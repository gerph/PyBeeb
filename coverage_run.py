#!/usr/bin/env python
"""
Main invocation, but with coverage.

SUT:    Integration tests
Area:   All tests within Integration test type
Class:  Statistical
Type:   Coverage
"""

import argparse

import importlib
import json
import os
import sys

import coverage

# Files we aren't interested in
omitted_paths = [
    ]
# Packages we will process
package = ['pybeeb']


def update_json_file_with_scm(jsonfile):
    """
    Adds extra information to the JSON file for source control information.

    The following values are set:
        meta.scm_branch: $CI_BRANCH
        meta.scm_hash: $CI_SHA
        meta.scm_id: $CI_BRANCH_VERSION
    """
    with open(jsonfile, 'r') as fh:
        report = json.load(fh)
    report['meta']['scm_branch'] = os.environ.get('CI_BRANCH', None)
    report['meta']['scm_hash'] = os.environ.get('CI_SHA', None)
    report['meta']['scm_id'] = os.environ.get('CI_BRANCH_VERSION', None)
    with open(jsonfile, 'w') as fh:
        json.dump(report, fh)


datafile = os.environ.get('COVERAGE_DATA', 'ci-logs/coverage/data')
htmldir = os.environ.get('COVERAGE_HTML', 'artifacts/coverage/html')
textfile = os.environ.get('COVERAGE_REPORT', 'artifacts/coverage/report.txt')
xmlfile = os.environ.get('COVERAGE_XML', None)
jsonfile = os.environ.get('COVERAGE_JSON', None)

datadir = os.path.dirname(datafile)
if not os.path.isdir(datadir):
    os.makedirs(datadir)
if not os.path.isdir(htmldir):
    os.makedirs(htmldir)
reportdir = os.path.dirname(textfile)
if not os.path.isdir(reportdir):
    os.makedirs(reportdir)
if xmlfile is None:
    if '.txt' in textfile:
        xmlfile = textfile.replace(".txt", ".xml")
    else:
        xmlfile += ".xml"
if jsonfile is None:
    if '.txt' in textfile:
        jsonfile = textfile.replace(".txt", ".json")
    else:
        jsonfile += ".json"


parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--module', default='PyBeebU',
                    help="Module to run with coverage")
parser.add_argument('--coverage-report', action='store_true', default=False,
                    help="Generate report for collected coverage information")
parser.add_argument('--clear', action='store_true', default=False,
                    help="Clear all the coverage information before running")

(options, unknown) = parser.parse_known_args()
sys.argv = [options.module + '.py'] + list(unknown)

package.append(options.module)

cov = coverage.Coverage(data_file=datafile, auto_data=True, branch=True, source=package, concurrency='thread')


if options.coverage_report:
    cov.load()

    print("Generate HTML report")
    cov.html_report(directory=htmldir, omit=omitted_paths)

    print("Generate text report")
    with open(textfile, 'w') as fh:
        coverage = cov.report(file=fh, omit=omitted_paths)

    print("Generate JSON report")
    coverage = cov.json_report(outfile=jsonfile, omit=omitted_paths)
    update_json_file_with_scm(jsonfile)

    print("Generate XML report")
    coverage = cov.xml_report(outfile=xmlfile, omit=omitted_paths)

    print("Overall Coverage: %.3f%%" % (coverage,))
    result = 0

else:
    if options.clear:
        cov.erase()
        result = 0
    else:
        # Reset the arguments to those that were passed on
        unknown.insert(0, sys.argv[0])
        sys.argv = unknown

        # Run pyro with coverage enabled
        cov.start()
        mod = importlib.import_module(options.module)
        sys.modules[options.module] = mod
        setattr(sys.modules['__main__'], options.module, mod)
        result = mod.main()
        cov.stop()

sys.exit(result)
