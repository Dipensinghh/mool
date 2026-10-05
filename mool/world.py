"""The user's own data: saved contacts and a verified registry. Trusted by construction."""
from __future__ import annotations
from dataclasses import dataclass, field

UPI_CIRCLE_PER_TXN_CAP = 5000  # today's UPI Circle full-delegation per-transaction cap


@dataclass(frozen=True)
class Contact:
    name: str
    upi: str
    aliases: tuple
    past_bills: tuple
    user_cap: int | None = None  # a per-payee limit the user set themselves
    biller: bool = False         # registered on Bharat Connect (formerly BBPS): amount comes from a bill fetch

    @property
    def amount_bound(self) -> int:
        """Largest amount Mool will accept from an untrusted document without asking."""
        if self.user_cap is not None:
            return self.user_cap
        return round(max(self.past_bills) * 1.25)


CONTACTS: tuple[Contact, ...] = (
    Contact("Ramesh Kirana", "ramesh.kirana@okaxis", ("ramesh", "रमेश", "kirana", "किराना"), (820, 910, 760, 850)),
    Contact("Lakshmi Milk Dairy", "lakshmidairy@oksbi", ("lakshmi", "dairy", "doodh", "दूध"), (1450, 1500, 1480)),
    Contact("Anand Medicals", "anandmedicals@okicici", ("anand", "medical", "dawai", "दवाई"), (640, 2100, 980)),
    Contact("Sharma Tuition", "sharmatuition@okhdfcbank", ("sharma", "tuition", "ट्यूशन"), (3000, 3000, 3000), user_cap=3000, biller=True),
    Contact("Kumar Press", "kumarpress@ybl", ("kumar", "press", "istri", "इस्त्री"), (380, 420, 300)),
    Contact("Gowda Vegetables", "gowdaveg@okaxis", ("gowda", "sabzi", "vegetable", "सब्ज़ी"), (510, 640, 590)),
    Contact("Fathima Tailors", "fathimatailors@paytm", ("fathima", "tailor", "darzi", "दर्ज़ी"), (900, 1200)),
    Contact("Joseph Water Supply", "josephwater@oksbi", ("joseph", "water", "paani", "पानी"), (600, 600, 650), biller=True),
    Contact("Reddy Gas Agency", "reddygas@okicici", ("reddy", "gas", "cylinder", "सिलेंडर"), (950, 980, 1010), biller=True),
    Contact("Iyer Newspapers", "iyernews@okhdfcbank", ("iyer", "newspaper", "akhbaar", "अख़बार"), (450, 480, 450)),
)


def find_contact_in(text: str) -> Contact | None:
    t = text.lower()
    for c in CONTACTS:
        if c.name.lower() in t or any(a.lower() in t for a in c.aliases):
            return c
    return None


def contact_by_upi(upi: str) -> Contact | None:
    return next((c for c in CONTACTS if c.upi == upi), None)
