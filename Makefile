# Manage operations on the repository.

run: coverage

clean:
	find . -name '*.pyc' -delete

coverage_clear:
	./coverage_run.py --clear

coverage_unittest_memory:
	./coverage_run.py --module MemoryTests

coverage_unittest_disassemble:
	./coverage_run.py --module DisassembleTest

coverage_inttest: \
		coverage_inttest_pybeeb_invoke \
		coverage_inttest_pybeeb_fs \
		coverage_inttest_pybeeb_stream \
		coverage_inttest_pybeeb_commands

# NOTE: None of these tests check the output to confirm that we're doing the right thing.
# Simple invocation test
coverage_inttest_pybeeb_invoke:
	./coverage_run.py --module RunBeeb < /dev/null

coverage_inttest_pybeeb_fs:
	printf '*.\n*. tests\nLOAD "Tests.helloworld"\nRUN' | ./coverage_run.py --module RunBeeb

coverage_inttest_pybeeb_stream:
	printf '*dir tests\nCHAIN "readfile"\n' | ./coverage_run.py --module RunBeeb

coverage_inttest_pybeeb_commands:
	printf '*FX0\n*QUIT\n' | ./coverage_run.py --module RunBeeb

coverage: \
	   coverage_clear \
	   coverage_unittest_memory \
	   coverage_unittest_disassemble \
	   coverage_inttest
	./coverage_run.py --coverage-report
