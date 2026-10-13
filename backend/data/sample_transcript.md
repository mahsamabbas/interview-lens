Interviewer: Thanks for joining. Tell me about your recent backend work.

Candidate: I have four years building Python services—mostly FastAPI—and I own internal REST APIs that handle uploads and background jobs.

Interviewer: How do you structure a typical API endpoint?

Candidate: Pydantic models for validation, dependency injection for DB connections, and thin handlers with a service layer.

Interviewer: Give an example of SQL you are comfortable writing.

Candidate: Joins across orders and customers, aggregations for dashboards, and indexes when queries slow down.

Interviewer: Walk me through designing a URL shortener at scale.

Candidate: I would store mappings in a database and cache hot links. I have not built one end to end, so sharding and collision handling are gaps for me.

Interviewer: How would you handle ten million writes per day?

Candidate: I have not operated at that scale—I would need to study partitioning and write-path bottlenecks with a senior architect.

Interviewer: How do you test API changes?

Candidate: pytest with TestClient, fixtures for temp databases, and mocks for external LLM calls so CI stays offline.
