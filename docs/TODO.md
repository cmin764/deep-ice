# ToDo

A list of future improvements to consider the solution complete.

## Requirements

Critical features and behaviour that isn't met yet.

- [x] Deferring long-running payments with [ARQ](https://arq-docs.helpmanual.io/).
- [x] Storing stats in Redis which can be later retrieved for analytics purposes.

## Developer Experience

Nice to have features improving the DX and aiding codebase robustness.

- [x] Invoke commands for running jobs easier, like: linting & formatting, sorting deps, testing, running the server, migrations etc.
- [ ] GitHub action to run linting checks and tests. (CI/CD)
- [ ] Documentation: class diagram, UX flowchart, microservice architecture, which shows how the system works.

## Next

Up next production-grade service improvements.

- Get ready for payment failures and ensure an _auto-retry_ mechanism within a given timeframe.
- Store errors in **Sentry**.
- Keep logs in **Logstash**.
- Send stats to **Elasticsearch**. (**Kibana**)
- Monitor system and app metrics with **Prometheus**. (**Grafana**)
