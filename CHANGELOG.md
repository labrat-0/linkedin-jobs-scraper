# Changelog

## 0.0.38

**Max Results was capped at 1,000 by mistake, and batch runs now warn instead of truncating quietly.**

`maxResults` caps the whole run, but it carried LinkedIn's *per query* limit of 1,000 as its maximum. That is the limit on a single search, which `maxResultsPerSearch` already enforces. The effect was that no batch run could return more than 1,000 rows in total, however many searches it contained, and raising the number was rejected with "This field should be <= 1000".

* **Max Results maximum raised from 1,000 to 10,000.** A 30 combination batch at 50 per search needs 1,500 and can now ask for it. Max Results Per Search stays at 1,000, which is LinkedIn's real per query limit.
* **Runs now warn when the configuration truncates the batch.** If Max Results is lower than combinations x Max Results Per Search, the run logs how many combinations will not execute and the exact number to set. Nothing is changed automatically, since results are billed per item and raising your run size without asking would raise your bill.
* Both field descriptions rewritten so the difference between the two caps is clear.

## 0.0.34 – 0.0.36

**Removed filters that LinkedIn was ignoring.**

If you used Work Arrangement, Job Type, Experience Level, or Salary, your past results were not filtered the way you expected. LinkedIn's logged-out endpoints accept these and then discard them. Verified through residential proxies: two runs of the same search, one On-site and one Remote, returned the identical 25 jobs in the same order. Only Date Posted is honored server side.

The `workplaceType` column was derived from the filter you selected rather than from the job, so every row in a remote search was labelled remote regardless of the actual arrangement.

What changed:

* **Removed** Work Arrangement (`workType`) and the `workplaceType` output column. LinkedIn publishes no per job workplace value to logged-out clients. The Hybrid/Remote chip on linkedin.com is logged-in UI only.
* **Removed** Minimum Salary (`salary`). Nothing in the public markup can back it. The `salary` output field is unchanged.
* **Job Type and Experience Level now work properly.** Instead of sending parameters LinkedIn drops, the actor verifies each job's published Employment type and Seniority level. Every returned row genuinely matches. Both enable Fetch Full Job Details automatically, which adds one request per job.
* LinkedIn publishes no seniority for roughly half of postings. With Experience Level set, those rows are dropped rather than guessed at, so expect fewer results than Max Results. Every run now reports how many rows were dropped for a real mismatch versus how many had nothing to check.
* **Fixed batch examples that silently truncated.** Several published examples set Max Results Per Search but left Max Results at its default 100. Max Results caps the whole run, so those examples stopped after two combinations and the rest never executed. If you copied one, raise Max Results to combinations x per search.

Need remote filtering? Put "remote" in your keywords, and/or enable Fetch Full Job Details and filter the `description` text. Both are heuristics over how postings are written, not verified flags.

Thanks to the user who reported this and kept pushing after my first answer was wrong.
