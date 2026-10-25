import pytest
from scripts.check_test_report import verify_report


def test_report_accepts_completed_cases(tmp_path):
    path=tmp_path/'junit.xml'
    path.write_text('<testsuites><testsuite><testcase name="one"/><testcase name="two"/></testsuite></testsuites>')
    assert verify_report(path)==2


@pytest.mark.parametrize('body',['','<testcase><skipped/></testcase>','<testcase><failure/></testcase>','<testcase><error/></testcase>'])
def test_report_rejects_false_green(tmp_path,body):
    path=tmp_path/'junit.xml';path.write_text('<testsuites><testsuite>'+body+'</testsuite></testsuites>')
    with pytest.raises(ValueError): verify_report(path)
