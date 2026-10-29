# -*- coding: utf-8 -*-
"""
Unit tests for the zero-Qt task layer (manga_translator.tasks / common.events).

These never import PySide6, so they run headless.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from manga_translator.common.events import EventHub  # noqa: E402
from manga_translator.tasks import TaskManager, TaskState  # noqa: E402


class TestEventHub(unittest.TestCase):

    def test_sub_and_publish(self):
        hub = EventHub()
        seen = []
        unsub = hub.subscribe("demo", lambda ev: seen.append(ev))
        hub.publish("demo", x=1)
        unsub()
        hub.publish("demo", x=2)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["type"], "demo")
        self.assertEqual(seen[0]["x"], 1)

    def test_wildcard_subscriber(self):
        hub = EventHub()
        seen = []
        hub.subscribe("*", lambda ev: seen.append(ev["type"]))
        hub.publish("a", v=1)
        hub.publish("b", v=2)
        self.assertEqual(seen, ["a", "b"])


class TestTaskManager(unittest.TestCase):

    def test_submit_runs_fn_and_emits_done(self):
        tasks = TaskManager(max_workers=2)
        events = []

        def record(ev):
            events.append(ev["type"])

        tasks.subscribe(record)

        def work(*, cancel_event, **kwargs):
            time.sleep(0.05)
            return 42

        task = tasks.submit(work, label="add")
        result_future = task  # Task has `.result` filled after done
        deadline = time.time() + 3
        while task.state not in (TaskState.DONE, TaskState.FAILED) and time.time() < deadline:
            time.sleep(0.01)
        tasks.shutdown()

        self.assertEqual(task.result, 42)
        self.assertIn("started", events)
        self.assertIn("done", events)

    def test_cancel(self):
        tasks = TaskManager(max_workers=2)
        task = tasks.submit(
            lambda *, cancel_event, **kwargs: (
                cancel_event.wait(2) or cancel_event.is_set()
            ),
            label="block",
        )
        time.sleep(0.05)
        ok = tasks.cancel(task.id)
        deadline = time.time() + 2
        while task.state not in (TaskState.CANCELLING, TaskState.DONE, TaskState.FAILED) \
                and time.time() < deadline:
            time.sleep(0.01)
        tasks.shutdown()
        self.assertTrue(ok)
        self.assertIn(task.state, (TaskState.CANCELLING, TaskState.FAILED, TaskState.DONE))

    def test_progress_updates_task(self):
        tasks = TaskManager(max_workers=1)

        def work(*, cancel_event, **kwargs):
            tasks.progress(next(iter(tasks._tasks)), 50, "halfway")
            return True

        task = tasks.submit(work, label="progress")
        deadline = time.time() + 2
        while task.state not in (TaskState.DONE, TaskState.FAILED) and time.time() < deadline:
            time.sleep(0.01)
        tasks.shutdown()
        self.assertEqual(task.progress, 100)  # marked complete


if __name__ == "__main__":
    unittest.main()