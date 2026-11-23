"""Trust pages: terms, privacy, contact, and the favicon.

Plain, factual pages — no policy is invented here that the operator has
not set. Payments are Bitcoin via BTCPay or card via Stripe; the site collects an email
address, uploaded CSVs, and generated reports, and nothing else; there
are no third-party trackers or ads.
"""

CONTACT_EMAIL = 'vincenthalay2005@gmail.com'

TERMS_HTML = '''<section class="panel narrow"><h1>Terms of Service</h1>
<p>VELXTRIA turns a small business's sales CSV into clean monthly and product reports.</p>
<h2>Accounts</h2>
<p>Creating an account is free. A free account gets 1 free report. PRO is $49 for 30 days with 50 reports per billing cycle.</p>
<h2>Payments</h2>
<p>Payments are Bitcoin through BTCPay or card through Stripe. PRO activates automatically once the payment settles — a redirect back to the site alone never activates PRO. A payment that never settles grants nothing.</p>
<h2>Your data</h2>
<p>You are responsible for the files you upload: only upload data you have the right to process. The instant demo processes your file once and never stores it; reports you generate from an account are stored on that account so you can view and download them.</p>
<h2>Acceptable use</h2>
<p>Do not use VELXTRIA to process data you do not have the right to handle, to abuse the service, or to misrepresent its output as anything other than a report generated from your own file.</p>
<h2>Availability</h2>
<p>The service is provided as-is. It is a preview: features may change, and reports should be checked against your own records before you rely on them for tax, payroll, or legal purposes.</p>
<h2>Liability</h2>
<p>Liability is limited to the amount you paid for the service in the 30 days before the claim.</p>
<h2>Changes</h2>
<p>These terms may change; the current version is always the one on this page.</p>
<p>Questions: <a href="/contact">contact us</a>.</p></section>'''

PRIVACY_HTML = '''<section class="panel narrow"><h1>Privacy Policy</h1>
<p>VELXTRIA collects as little as possible, and sells nothing.</p>
<h2>What we collect</h2>
<ul>
<li><b>Account:</b> your email address and password (stored hashed).</li>
<li><b>Your files:</b> the sales CSVs you upload, and the reports generated from them. The instant demo is the exception: your file is processed once and never stored.</li>
<li><b>Payments:</b> BTCPay verifies a Bitcoin payment and Stripe verifies a card payment; each tells us whether it settled. We never see your card details or your wallet.</li>
<li><b>Usage counts:</b> how many reports you have generated, so the free and PRO limits can be enforced, and anonymous funnel counts (page views, demo runs, sign-ups) with no personal data attached.</li>
</ul>
<h2>Cookies</h2>
<p>First-party cookies only: a session cookie while you are signed in, a referral cookie (30 days) when you arrive through someone's referral link, and a demo cookie (10 minutes) so a demo report can be claimed after you sign up. No third-party trackers, no ads.</p>
<h2>Sharing</h2>
<p>Your data is not sold or shared, except with BTCPay or Stripe to verify a payment, and as required by law.</p>
<h2>Your data</h2>
<p>Reports you generate stay on your account so you can view and download them. To ask about your data, email <a href="mailto:''' + CONTACT_EMAIL + '''">''' + CONTACT_EMAIL + '''</a>.</p></section>'''

CONTACT_HTML = '''<section class="panel narrow"><h1>Contact</h1>
<p>Questions about VELXTRIA, a report, or a payment? Email us:</p>
<p><a href="mailto:''' + CONTACT_EMAIL + '''">''' + CONTACT_EMAIL + '''</a></p>
<p>Include the email address on your account and, for a payment question, the BTCPay invoice ID or Stripe session ID if you have it. We answer as fast as we can — this is a small operation.</p></section>'''

FAVICON_SVG = (b'<?xml version="1.0" encoding="UTF-8"?>\n'
               b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
               b'<rect width="64" height="64" rx="14" fill="#070811"/>'
               b'<text x="32" y="42" font-family="Arial,sans-serif" font-size="28"'
               b' font-weight="bold" fill="#a888ff" text-anchor="middle">VX</text>'
               b'</svg>')
