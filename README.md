# YouTube Finance Automation (GitHub Actions)
1. রিপোজিটরি **Public** রাখুন (Public হলে Actions ফ্রি)।
2. সব ফাইল আপলোড করুন (ফোল্ডার কাঠামোসহ; workflows যাবে `.github/workflows/` এ)।
3. Settings → Secrets and variables → Actions → New repository secret:
   YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
4. Settings → Actions → General → Workflow permissions → **Read and write permissions** → Save
5. ম্যানুয়াল রান: Actions ট্যাব → "Long Video" বা "Short Video" → **Run workflow** বাটন। শেষে নিজে পাবলিশ হবে।

অটো শিডিউল (ঢাকা সময়): Long 12:00 AM ও 12:00 PM, Short 6:00 AM ও 6:00 PM (cron UTC-তে দেওয়া)
