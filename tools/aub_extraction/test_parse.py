"""Parser tests against the real getRestrictions response for EECE 290, Summer 2024-25 (CRN 30314)."""
from add_restrictions import parse_restrictions, summarize

SAMPLE = """
<section aria-labelledby="restrictions">
    <div class="infoicon"><span class="status-bold">Not all restrictions are applicable.</span></div> <br/>
            <span class="status-bold">Must be enrolled in one of the following Classes:</span><br/>
                <span class="detail-popup-indentation">Engineering 1</span><br/>
                <span class="detail-popup-indentation">2 (E1)</span><br/>
                <span class="detail-popup-indentation">Engineering 3</span><br/>
                <span class="detail-popup-indentation">4</span><br/>
                <span class="detail-popup-indentation">5(E2)</span><br/>
        <br/>
                    <span class="status-bold">Must be enrolled in one of the following Fields of Study (Major, Minor or Concentration):</span> <br/>
                    <span class="detail-popup-indentation">Computer &amp; Communications Eng. (ECMP)</span><br/>
                    <span class="detail-popup-indentation">Electrical &amp; Computer Eng&#39;g (EECE)</span><br/>
                </br>
        <br/>
</section>
"""


def test_real_sample():
    rules, names = parse_restrictions(SAMPLE)
    assert rules == [("+", "Classes", ["E1", "E2"]), ("+", "Fields of Study", ["ECMP", "EECE"])]
    assert names[("Classes", "E1")] == "Engineering 1, 2"
    assert names[("Fields of Study", "ECMP")] == "Computer & Communications Eng."
    assert summarize(rules) == {"restrictions": "+Classes=E1,E2;+Fields of Study=ECMP,EECE",
                                "classes_allowed": "E1,E2", "majors_allowed": "ECMP,EECE",
                                "departments_allowed": ""}


def test_majors_label_and_departments():
    rules = [("+", "Classes", ["SO"]), ("+", "Majors", ["CHME", "ECMP"]),
             ("+", "Fields of Study", ["ECMP", "EECE"]), ("+", "Departments", ["IEEM", "MCEG"])]
    s = summarize(rules)
    assert s["majors_allowed"] == "CHME,ECMP,EECE"
    assert s["departments_allowed"] == "IEEM,MCEG"


def test_no_restrictions():
    rules, _ = parse_restrictions('<section aria-labelledby="restrictions"></section>')
    assert summarize(rules)["restrictions"] == "NONE"


def test_cannot_be_enrolled_is_not_allowed():
    frag = ('<span class="status-bold">Cannot be enrolled in one of the following Classes:</span>'
            '<span class="detail-popup-indentation">Freshman (FR)</span>')
    rules, _ = parse_restrictions(frag)
    assert rules == [("-", "Classes", ["FR"])]
    assert summarize(rules)["classes_allowed"] == ""
