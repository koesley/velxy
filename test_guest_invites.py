import sqlite3
import unittest
import guest_invites

class GuestInvitationTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        guest_invites.setup(self.db)
    def tearDown(self):
        self.db.close()
    def test_one_time_redeem(self):
        token = guest_invites.create(self.db, hours=24, clock=1000)
        self.assertTrue(guest_invites.redeem(self.db, token, 42, clock=1001))
        self.assertTrue(guest_invites.active(self.db, 42, clock=1002))
        self.assertFalse(guest_invites.redeem(self.db, token, 43, clock=1002))
        self.assertFalse(guest_invites.active(self.db, 42, clock=1000+86400))
    def test_expired_invitation(self):
        token = guest_invites.create(self.db, hours=1, clock=1000)
        self.assertFalse(guest_invites.redeem(self.db, token, 42, clock=4600))
    def test_invalid_tokens(self):
        self.assertFalse(guest_invites.redeem(self.db, "", 42))
        self.assertFalse(guest_invites.redeem(self.db, "x"*300, 42))
        with self.assertRaises(ValueError):
            guest_invites.create(self.db, hours=999)
    def test_token_not_stored_plaintext(self):
        token = guest_invites.create(self.db, clock=1000)
        self.assertNotEqual(self.db.execute("SELECT token_hash FROM guest_invites").fetchone()[0], token)

if __name__ == "__main__":
    unittest.main()
