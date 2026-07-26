from caiguard.engine import classify_section, meaning, semantic_hash, content_hash
def lvl(o,n):
    r=classify_section(o,n); return "weakened" if r.get("weak") else r["level"]
def test_cases():
    assert lvl("The Contractor SHALL maintain $2,000,000 coverage.","The Contractor SHALL maintain $2,000,000 coverage.")=="none"
    assert lvl("A B C","A  B   C")=="cosmetic"
    assert lvl("limit of $2,000,000 per occurrence","limit of $1,000,000 per occurrence")=="semantic"
    assert lvl("Contractor MUST indemnify Owner","Contractor SHOULD indemnify Owner")=="weakened"
    assert lvl("within 30 days","within 15 days")=="semantic"
    assert lvl("parties agree to cooperate fully","parties agree to cooperate in good faith")=="cosmetic"
    assert lvl("This is a long clause with many detailed obligations across the whole section body here now today.","Short.")=="structural"
    assert content_hash("x")!=content_hash("y")
    assert semantic_hash("MUST pay $5")!=semantic_hash("MUST pay $9")
    print("engine: all cases pass")
if __name__=="__main__":
    test_cases()
