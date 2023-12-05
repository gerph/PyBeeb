# Run our tests

coverage_clear:
	./coverage_run.py --clear

coverage_unittest_memory:
	./coverage_run.py --module MemoryTests

coverage_unittest_disassemble:
	./coverage_run.py --module DisassembleTest

coverage_inttest_pybeebu:
	./coverage_run.py --module PyBeebU < /dev/null

coverage: \
	   coverage_clear \
	   coverage_unittest_memory \
	   coverage_unittest_disassemble \
	   coverage_inttest_pybeebu
	./coverage_run.py --coverage-report
