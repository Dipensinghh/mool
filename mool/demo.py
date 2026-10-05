"""Terminal demo:  python -m mool.demo  [attack name]"""
import sys
from attacks.scenarios import ATTACKS, clean
from mool.agents import MoolAgent, NaiveAgent
from mool.rail import MockUPIRail
from mool.receipt import verify_receipt
from mool.world import CONTACTS

RED, GREEN, AMBER, DIM, END = "\033[31m", "\033[32m", "\033[33m", "\033[2m", "\033[0m"


def main():
    name = " ".join(sys.argv[1:]) or "Hidden text in a PDF"
    scen = {"Clean bill": clean, **ATTACKS}
    if name not in scen:
        sys.exit(f"Unknown attack. Choose one of: {', '.join(scen)}")
    c, cmd = CONTACTS[0], "Ramesh Kirana ka grocery bill pay kar do"
    docs = scen[name](c, 1040)
    print(f"\nAai: \"{cmd}\"    attack: {name}\n")
    for d in docs:
        print(f"{DIM}--- {d.source} (untrusted) ---\n{d.text}{END}\n")
    n = NaiveAgent().run(cmd, docs, MockUPIRail())
    if n.credit:
        col = GREEN if n.credit.upi == c.upi else RED
        print(f"Without Mool: {col}{n.credit.soundbox}{END}   checks: {', '.join(n.reasons)}")
    else:
        print(f"Without Mool: {n.verdict} ({'; '.join(n.reasons)})")
    m = MoolAgent().run(cmd, docs, MockUPIRail())
    if m.credit:
        print(f"With Mool:    {GREEN}{m.credit.soundbox}{END}")
        print(f"  receipt signature valid: {verify_receipt(m.receipt)}")
    else:
        print(f"With Mool:    {AMBER}HOLD{END}, no money moved. Asks Aai: \"{m.question}\"")
    for r in m.reasons:
        print(f"  - {r}")
    print()


if __name__ == "__main__":
    main()
