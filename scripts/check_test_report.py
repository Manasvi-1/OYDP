"""Fail acceptance CI on empty, skipped or unsuccessful JUnit reports."""
import argparse
from pathlib import Path
from xml.etree import ElementTree


def verify_report(path: Path) -> int:
    root=ElementTree.parse(path).getroot()
    cases=list(root.iter('testcase'))
    if not cases:
        raise ValueError('Acceptance report contains no test cases')
    for case in cases:
        if any(case.find(tag) is not None for tag in ('skipped','failure','error')):
            raise ValueError('Acceptance report includes skipped or unsuccessful cases')
    return len(cases)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report',type=Path)
    args=parser.parse_args()
    try:
        print(f'Acceptance report verified: {verify_report(args.report)} cases; zero skips/failures')
    except (ValueError,ElementTree.ParseError,OSError) as exc:
        raise SystemExit(str(exc)) from None
