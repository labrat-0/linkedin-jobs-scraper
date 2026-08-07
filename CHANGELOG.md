# Changelog

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
