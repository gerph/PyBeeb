"""
Console input and output management.
This module needs to manage the interface to the host system using whatever interfaces
are present. Because this is highly dependant on the host system, we have different
implementations for the POSIX style systems (macOS and Linux), and Windows. No
RISC OS implementation is present - it needs more work to make that happen.
"""

import errno
import os
try:
    import Queue
    queue = Queue
except ImportError:
    import queue
import sys
import threading
import time


class ConsoleBase(object):
    """
    Console management from the host enviroment.
    """
    _singleton = None
    _inited = False

    def __new__(cls, *args, **kwargs):
        #print("Singleton creation %r" % (cls._singleton))
        if not cls._singleton:
            cls._singleton = super(ConsoleBase, cls).__new__(cls, *args, **kwargs)
        return cls._singleton

    # FIXME: It's arguable that the console input should run continually in a thread
    #        and push keys into buffers.

    def __init__(self):
        if not self._inited:
            super(ConsoleBase, self).__init__()
            self.terminal_active = False
            self.cooked_newlines = True
            self.output = sys.stdout
            self._inited = True

    def terminal_init(self):
        self.terminal_active = True

    def terminal_reset(self):
        self.terminal_active = False

    def encode(self, uni):
        """
        Encode a UTF-8 sequence into the 8-bit form
        """
        return uni.encode('latin-1')

    def write(self, message):
        """
        Write a message to the actual console.
        """
        #sys.stderr.write("<|%r|%r>" % (message, self.output))
        if not self.cooked_newlines:
            message = message.replace('\n', '\r\n')
        self.output.write(message)

    def writeln(self, message):
        self.write(message + '\n')

    def flush(self):
        self.output.flush()

    def finalise(self):
        if self.__class__ == ConsoleBase:
            # We don't want the base class messing with our configuration.
            return

        if self.terminal_active:
            self.terminal_reset()

    def getch(self, timeout=None):
        return None

    def handle_eof(self):
        """
        Do whatever you need to when an EOF is received from the host.

        @return: True if we handled it; False if there was nothing done.
        """
        return False


class ConsoleConfig(object):
    flush_output_on_read = True
    input_escapes = True
    input_escapes_timeout = 0.2
    input_utf8 = True
    input_backspace_code = 127


try:
    import array
    import fcntl
    import select
    import termios
    import tty

    # We're on a POSIX-like system, so we should be able to use its configuration.

    class Console(ConsoleBase):
        # Letter sequences have been stripped of the modifier if the modifier was '1'.
        #   [1A => [A
        # ~ sequences have been stripped of the modifier if the modifier was '1'.
        #   [24;1~ => [24~
        escape_codes = {
                # Standard sequences
                b'[A': b'\x8F', # Up
                b'[B': b'\x8E', # Down
                b'[C': b'\x8D', # Right
                b'[D': b'\x8C', # Left
                b'[F': b'\x8B', # End (Copy in RISC OS terms)
                b'[H': b'\x1E', # Home
                b'[Z': b'\x09', # Shift-Tab

                # Application sequences
                b'OP': b'\x81', # F1
                b'OQ': b'\x82', # F2
                b'OR': b'\x83', # F3
                b'OS': b'\x84', # F4
                b'OH': b'\x1E', # Home
                b'OF': b'\x8B', # End

                # VT sequences
                b'[1~': b'\x1E', # Home (don't know what this should be)
                #b'[2~': b'\x89', # Insert (don't know what this should be)
                b'[3~': b'\x7F', # Delete
                b'[4~': b'\x8B', # End
                b'[5~': b'\x9F', # Page Up
                b'[6~': b'\x9E', # Page Down
                b'[7~': b'\x1E', # Home
                b'[8~': b'\x87', # End
                b'[11~': b'\x81', # F1
                b'[12~': b'\x82', # F2
                b'[13~': b'\x83', # F3
                b'[14~': b'\x84', # F4
                b'[15~': b'\x85', # F5
                # Note 16 isn't mapped
                b'[17~': b'\x86', # F6
                b'[18~': b'\x87', # F7
                b'[19~': b'\x88', # F8
                b'[20~': b'\x89', # F9
                b'[21~': b'\xCA', # F10
                # Note 22 isn't mapped
                b'[23~': b'\xCB', # F11
                b'[24~': b'\xCC', # F12

                b'[25~': b'\x80', # Print (don't know what this should be)

                # Shifted keys
                b'[1;2P': b'\x91', # Shift-F1
                b'[1;2Q': b'\x92', # Shift-F2
                b'[1;2R': b'\x93', # Shift-F3
                b'[1;2S': b'\x94', # Shift-F4
                b'[15;2~': b'\x95', # Shift-F5
                b'[17;2~': b'\x96', # Shift-F6
                b'[18;2~': b'\x97', # Shift-F7
                b'[19;2~': b'\x98', # Shift-F8
                b'[20;2~': b'\x99', # Shift-F9
                b'[21;2~': b'\xDA', # Shift-F10
                b'[23;2~': b'\xDB', # Shift-F11
                b'[24;2~': b'\xDC', # Shift-F12

                b'[1;2A': b'\x9F', # Shift-Up
                b'[1;2B': b'\x9E', # Shift-Down
                b'[1;2C': b'\x9D', # Shift-Right
                b'[1;2D': b'\x9C', # Shift-Left
                b'[1;2F': b'\x9B', # Shift-End (Copy in RISC OS terms)
                b'[1;2H': b'\x1E', # Shift-Home

                # Ctrled keys
                b'[1;5H': b'\x1E', # Ctrl-Home
                b'[1;5F': b'\xAB', # Ctrl-End (Copy in RISC OS terms)
            }

        def __init__(self):
            if not self._inited:
                super(Console, self).__init__()
                self.fd = None
                self.is_tty = False
                self.is_dead = False
                self.old_settings = None
                self.intbuf = array.array('i', [0])
                self.config = ConsoleConfig()
                self.original_stdout = sys.__stdout__

                # ANSI Escape handling
                self.in_utf8_sequence = []
                self.in_escape_sequence = []
                self.in_utf8 = False
                self.in_escape = None

                self.debug_inputescapes = False
                self.debug_inpututf8 = False

        def get_fd(self):
            try:
                return sys.stdin.fileno()
            except AttributeError:
                return None

        def get_isatty(self):
            try:
                return sys.stdin.isatty()
            except AttributeError:
                return False

        def terminal_init(self):
            if not self.terminal_active:
                if not self.is_dead:
                    self.fd = self.get_fd()
                    self.is_tty = self.get_isatty()

                if self.is_tty:
                    try:
                        # Preserve old settings
                        self.old_settings = termios.tcgetattr(self.fd)

                        # Set up our requirements
                        tty.setraw(self.fd, termios.TCSANOW)
                        new_settings = termios.tcgetattr(self.fd)

                        # Output post processing (LF => CR, LF mostly) only if requested
                        if self.cooked_newlines:
                            new_settings[1] = new_settings[1] | termios.OPOST | termios.ONLCR

                        # Allow interrupt signals
                        new_settings[3] = new_settings[3] | termios.ISIG

                        # Allow a single byte to be read
                        new_settings[6][termios.VMIN] = b'\x01'
                        new_settings[6][termios.VTIME] = b'\x00'

                        termios.tcsetattr(self.fd, termios.TCSANOW, new_settings)
                    except termios.error as exc:
                        if exc.args[0] == errno.EIO:
                            self.is_dead = True
                            self.is_tty = False
                        else:
                            raise
                if not self.cooked_newlines:
                    sys.stdout = self

            super(Console, self).terminal_init()

        def terminal_reset(self):
            if self.terminal_active:
                if self.is_tty:
                    termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
                if not self.cooked_newlines:
                    sys.stdout = self.original_stdout
            super(Console, self).terminal_reset()

        def parse_utf8(self, seq):
            """
            Parse from a UTF-8 sequence into a sequence that we can insert literally.
            """
            seq = b''.join(seq)
            # Decode the sequence from UTF-8
            decoded = seq.decode('utf-8', 'replace')
            if self.debug_inpututf8:
                print("Input UTF-8: Sequence %r => %r" % (seq, decoded))

            # Encode the sequence into the current alphabet
            rostr = self.encode(decoded)
            if len(rostr) == 1:
                return (b'\x00', rostr)
            else:
                acc = []
                for c in rostr:
                    acc.extend((b'\x00', c))
                return acc

        def parse_escape(self, seq):
            if len(seq) == 0 or (len(seq) == 1 and seq[0] == b'\x1b'):
                # Literal escape key!
                # FIXME: Should we set the escape flags here too?
                return b'\x1b'

            if seq[0] == b'[':
                code = seq[-1]
                if (code >= b'A' and code <= b'Z') or (code >= b'a' and code <= b'z'):
                    # letter codes might have numbers preceding them for modifiers.
                    # a modifier of 1 means 'no modifier', so we can strip it
                    if len(seq) == 3 and seq[1] == b'1':
                        # Reduce it to the un-modifier version so our dictionary is simpler
                        seq = [b'[', code]
                elif code == b'~':
                    # The [<num>;<modifier>~ sequence can also have a modifier of 1,
                    # so we simplify this as well.
                    if len(seq) > 3 and seq[-3] == b';' and seq[-2] == b'1':
                        seq = seq[:-3]
                        seq.append(b'~')
                # FIXME: The modifier might be +1 for Shift, +2 for Alt, +4 for Ctrl

            seq = b''.join(seq)
            value = self.escape_codes.get(seq, None)
            if self.debug_inputescapes:
                if value:
                    print("Input escape: Sequence %r => %r" % (seq, value))
                else:
                    print("Input escape: Sequence %r not recognised" % (seq,))
            return value

        def getch(self, timeout=None):
            # Ensure that if they gave us a prompt or line buffered content, it's actually been output
            if self.config.flush_output_on_read:
                self.flush()

            # Enable this option if you're trying to debug the underlying input system without
            # the escape and UTF-8 handling getting in the way.
            if False:
                return self.int_getch(timeout=timeout)

            if not self.in_escape and not self.in_utf8:
                now = time.time()
                ch = self.int_getch(timeout=timeout)
                if ch == b'\x7F':
                    ch = bytes(bytearray([self.config.input_backspace_code]))
                if ch == b'\x1b' and self.config.input_escapes:
                    # This is an escape character, so we're starting a sequence
                    self.in_escape = time.time()
                    self.in_escape_sequence = []
                    # Work out how much more time we have left until the user's request times out
                    if timeout is not None:
                        timeout -= time.time() - now
                elif ch >= b'\x80' and self.config.input_utf8:
                    # Likely to be the start of a UTF-8 sequence.
                    if ch >= b'\xc0' and ch <= b'\xf7':
                        # Is a UTF-8 sequence start
                        self.in_utf8_sequence = [ch]
                        if ch >= b'\xf0':
                            self.in_utf8 = 4
                        elif ch >= b'\xe0':
                            self.in_utf8 = 3
                        else:
                            self.in_utf8 = 2
                    else:
                        # It's not a valid introducing character; so treat it literally
                        if self.debug_inpututf8:
                            print("Input UTF-8: Invalid introducer %r" % (ch,))
                        return (0, ch)
                else:
                    return ch

            if self.in_escape:
                # We know we're in an escape sequence, and we have timeout seconds left.
                while (timeout is None or timeout > 0) and self.in_escape:
                    now = time.time()
                    if timeout and timeout > self.config.input_escapes_timeout:
                        escape_timeout = timeout
                    else:
                        escape_timeout = self.config.input_escapes_timeout
                    ch = self.int_getch(timeout=escape_timeout)
                    if ch is None:
                        break
                    # Escapes end with a ~, A-Z, a-z (or a timeout)

                    self.in_escape_sequence.append(ch)
                    # In 'application ' mode, some sequences are sent as SS3 followed by a sequence
                    # SS3 => <esc>O followed by any character.
                    if self.in_escape_sequence[0] == b'O':
                        if len(self.in_escape_sequence) == 2:
                            # SS3 only applies to the next character.
                            self.in_escape = False
                            break
                    else:
                        if (ch >= b'A' and ch <= b'Z') or (ch >= b'a' and ch <= b'z') or ch == b'~':
                            # This is the end of a sequence
                            self.in_escape = False
                            break

                        if len(self.in_escape_sequence) == 1 and ch != b'[':
                            # This is an <esc><char> sequence
                            self.in_escape = False
                            break

                    # Work out how much more time we have left until the user's request times out
                    if timeout is not None:
                        timeout -= time.time() - now

                if self.in_escape and time.time() > self.in_escape + self.config.input_escapes_timeout:
                    self.in_escape = False

                if not self.in_escape:
                    # Decode the escape sequence
                    return self.parse_escape(self.in_escape_sequence)

            else:
                # We're in a UTF-8 sequence, so we handle this in a similar way but with
                # different terminal conditions
                while timeout > 0 and self.in_utf8:
                    now = time.time()
                    ch = self.int_getch(timeout=timeout)
                    if ch is None:
                        return None
                    if ch < b'\x80' or ch >= b'\xc0':
                        # This is not a character that should be in the UTF-8 sequence - it's
                        # broken UTF-8.
                        if self.debug_inpututf8:
                            print("Input UTF-8: Invalid sequence %r + %r" % (self.in_utf8_sequence, ch))

                        # FIXME: Configurable way to handle this?
                        acc = b''.join(self.in_utf8_sequence)
                        # FIXME: Discard the characters if wanted, or encode?
                        if ch < b'\x80':
                            # The excess is a plain character
                            # FIXME: Note that this doesn't handle the excess character being
                            #        an escape (!)
                            if acc:
                                acc += ch
                            self.in_utf8 = False
                        else:
                            # The excess is the start of another UTF-8 sequence, so we
                            # start another sequence
                            self.in_utf8_sequence = [ch]
                            if ch >= b'\xf0':
                                self.in_utf8 = 4
                            elif ch >= b'\xe0':
                                self.in_utf8 = 3
                            else:
                                self.in_utf8 = 2
                        return acc

                    self.in_utf8_sequence.append(ch)
                    if len(self.in_utf8_sequence) == self.in_utf8:
                        # We've reached the end of the sequence
                        self.in_utf8 = False
                        return self.parse_utf8(self.in_utf8_sequence)

                    # Work out how much more time we have left until the user's request times out
                    timeout -= time.time() - now

                return None

        def is_pending(self, timeout=None):
            input_pending = False

            # First check if there are bytes still to read
            try:
                fcntl.ioctl(self.fd, termios.FIONREAD, self.intbuf)
                if self.intbuf[0] > 0:
                    input_pending = True
            except IOError:
                # If the device doesn't support FIONREAD, we roll on to the select
                pass

            if not input_pending:
                # And check for new bytes (within the timeout)
                try:
                    r, w, x = select.select([self.fd], [], [], timeout)
                    if r:
                        input_pending = True
                except select.error as exc:
                    if exc[0] == errno.EINTR:
                        return False
                    else:
                        raise

            return input_pending

        def int_getch(self, timeout=None):
            ch = None
            if timeout is not None:
                before = time.time()
                if self.is_pending(timeout):
                    if self.is_tty:
                        # Ensures that we avoid Python's greedy read in the sys.stdin file handle
                        # which would otherwise consume more characters, preventing the select
                        # from being aware that the characters are present.
                        try:
                            ch = os.read(self.fd, 1)
                        except OSError as exc:
                            # Interrupted system call happens in cases like ctrl-z being pressed.
                            if exc.errno != errno.EINTR:
                                raise
                            ch = None
                    else:
                        ch = sys.stdin.read(1)
                    if ch == b'':
                        if not self.handle_eof() and timeout is not None:
                            # We didn't do anything, but the handle reported EOF.
                            # We're just going to wait for the timeout period, because otherwise
                            # we'll just busy wait.
                            took = time.time() - before

                            # For reasons that are unclear, when run under gitlab-runner under MacOS, the
                            # sleep time here is 5x longer than that we expect, which causes ticks to be
                            # missed. It is not clear why this happens. However, sleeping smaller fractions
                            # of the time requested and then waiting until the timeout has expired seems to
                            # be the only sensible way to deal with this.
                            while time.time() < before + timeout:
                                # Sleep in smaller chunks than the requested, so that we don't overrun the
                                # timeout point by much.
                                time.sleep(max(timeout - took, 0) / 10)

                        ch = None

            else:
                if self.fd is not None:
                    try:
                        ch = os.read(self.fd, 1)
                    except OSError as exc:
                        # Interrupted system call happens in cases like ctrl-z being pressed.
                        if exc.errno != errno.EINTR:
                            raise
                        ch = None
                else:
                    ch = sys.stdin.read(1)

            return ch

except ImportError:
    # We're on a Windows-like system; this is entirely tentative as I've never used Pyromaniac on there
    import msvcrt

    class Console(ConsoleBase):
        # Escape codes found by printing out the codes from the getch calls, below
        # Escape codes are preceded by 0x00, or 0xE0.
        escape_codes = {
            # Standard sequences
            'H': '\x8F', # Up
            'P': '\x8E', # Down
            'M': '\x8D', # Right
            'K': '\x8C', # Left
            'O': '\x8B', # End (Copy in RISC OS terms)
            'I': '\x9F', # Page Up
            'Q': '\x9E', # Page Down
            #'R': '\x99', # Insert (don't know what this should be)
            #'S': '\x99', # Delete (don't know what this should be)
            #'G': '\x8A', # Home (don't know what this should be)
            ';': '\x81', # F1
            '<': '\x82', # F2
            '=': '\x83', # F3
            '>': '\x84', # F4
            '?': '\x85', # F5
            '@': '\x86', # F6
            'A': '\x87', # F7
            'B': '\x88', # F8
            'C': '\x89', # F9
            'D': '\x8A', # F10
            'E': '\x8B', # F11
            'F': '\x8C', # F12

            #'': '\x80', # Print (don't know what this should be, and can't trigger it)
        }

        def __init__(self):
            if not self._inited:
                #print("Windows terminal started")
                super(Console, self).__init__()
                self.config = ConsoleConfig()
                self.thread = None
                self.alive = True
                self.want_key = threading.Event()
                self.input_queue = queue.Queue()

        def finalise(self):
            if self.thread:
                if self.want_key.is_set():
                    # We're currently waiting for a key, so we need to push a character
                    # into the msvcrt buffer, so that that request exits.
                    # This message will ONLY appear if you exit the application and the
                    # msvcrt was waiting for a key press on the console.
                    print("System exited; please press a key")
                    # This just causes us to stall until the keypress we were waiting on
                    # has been entered - probably because there's a mutex inside msvcrt.
                    # If we DON'T do this, the console will be left in a bad state where
                    # the keys that are input are the entire input (eg you press a key
                    # and then cmd says "unknown command <key you pressed>").
                    msvcrt.putch(' ')

                # Setting the 'want_key' will cause the input pump to wake up
                self.want_key.set()
                self.alive = False

                # Wait for runner to exit
                start = time.time()
                while self.thread and time.time() - start < 1.0:
                    # Wait until that thread exits (or we give up)
                    time.sleep(0.01)
                if self.thread:
                    print("Console: WARNING: Input pump thread failed to terminate")

        def start_thread(self):
            self.thread = threading.Thread(name='Console', target=self.runner)
            self.thread.daemon = True
            self.thread.start()

        def runner(self):
            # Data pump for console input
            #print("Input data pump running")
            polling_period = 0.5
            while self.alive:
                key_requested = self.want_key.wait(polling_period)
                if self.alive and key_requested:
                    # Block here reading the key from the console
                    key = msvcrt.getch()
                    self.want_key.clear()
                    self.input_queue.put(key)

            # We're exiting, so set the thread to None
            self.thread = None

        def int_getch(self, timeout=None):
            self.want_key.set()
            try:
                key = self.input_queue.get(True, timeout)
            except Queue.Empty:
                # No data, so return None
                return None

            if key in ('\x00', '\xe0'):
                # These magic values precede the escaped codes for the function and cursor keys.
                # So now we need another character to check which key it is.
                self.want_key.set()
                try:
                    second_key = self.input_queue.get(self.config.input_escapes_timeout)
                except Queue.Empty:
                    # No data, so return the first key
                    return key

                riscos_key = self.escape_codes.get(second_key, None)
                return riscos_key

            return key

        def is_pending(self, timeout=None):
            # FIXME: Not sure how to check if there's any input pending, so just say that there is.
            return True

        def getch(self, timeout=None):
            # Ensure that if they gave us a prompt or line buffered content, it's actually been output
            if self.config.flush_output_on_read:
                self.flush()

            if not self.thread:
                self.start_thread()

            key = self.int_getch(timeout)
            return key
