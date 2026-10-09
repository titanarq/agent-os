"""Can more work run at once right now: `python -m agent_os.product.dispatch headroom`.

Read-only. For every issue a v2 host has in the ready state it says whether `worker_task.sh start`
would let it start now or what it waits for. The rules are not restated here: dependencies and
touched code come from `agent_os.product.dispatch.rules`, and the cap is the one the driver
enforces (`planner.max_parallel_issues` and the `slots` of each backend).
"""
