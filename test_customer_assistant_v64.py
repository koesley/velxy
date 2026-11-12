import sqlite3
import unittest
from unittest.mock import patch
import customer_assistant_v64 as assistant
import business_collaboration_v62 as widget
import business_agents_v59 as agents

class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.access=patch.object(agents.core,"access",return_value="owner")
        self.audit=patch.object(agents.core,"audit")
        self.access.start();self.audit.start()
    def tearDown(self):
        self.access.stop();self.audit.stop();self.c.close()
    def test_published_faq_and_no_private_memory(self):
        agents.add_knowledge(self.c,1,"a","faq","What are your hours?","9am to 5pm")
        agents.add_knowledge(self.c,1,"a","memory","Password","SECRET")
        token=widget.publish(self.c,1,"a",True)
        with patch.dict("os.environ",{"VELXTRIA_V64_CHAT_ENABLED":"0"}):
            result=assistant.respond(self.c,token,"What are your hours?")
        self.assertEqual(result["answer"],"9am to 5pm")
        page=assistant.page(self.c,token,"What are your hours?")
        self.assertNotIn("SECRET",page)
    def test_model_only_sees_public_faq(self):
        agents.add_knowledge(self.c,1,"a","faq","Refund policy","30 days")
        agents.add_knowledge(self.c,1,"a","memory","Secret","PRIVATE")
        token=widget.publish(self.c,1,"a",True)
        seen=[]
        def model(q,context):
            seen.extend(context)
            return "Please review the 30 day refund policy."
        answer=assistant.respond(self.c,token,"How do refunds work?",model_call=model)
        self.assertEqual(answer["mode"],"ai_assisted")
        self.assertNotIn("PRIVATE",str(seen))
    def test_revoked_token_and_fallback(self):
        token=widget.publish(self.c,1,"a",True)
        widget.publish(self.c,1,"a",False)
        self.assertIsNone(assistant.respond(self.c,token,"Hello"))
    def test_html_escape(self):
        agents.add_knowledge(self.c,1,"a","faq","Hello there","<script>bad</script>")
        token=widget.publish(self.c,1,"a",True)
        with patch.dict("os.environ",{"VELXTRIA_V64_CHAT_ENABLED":"0"}):
            page=assistant.page(self.c,token,"Hello there")
        self.assertNotIn("<script>",page)

if __name__=="__main__":unittest.main()
