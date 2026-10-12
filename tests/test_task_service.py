import threading
import time
import unittest

from services.task_service import EventKind, TaskService


def _wait(svc, pred, timeout=3.0):
    events, end = [], time.time() + timeout
    while time.time() < end and not pred(events):
        events += svc.poll()
        time.sleep(0.01)
    return events


class TaskServiceTests(unittest.TestCase):
    def setUp(self):
        self.svc = TaskService()

    def tearDown(self):
        self.svc.shutdown()

    def test_result_and_progress(self):
        def work(ctx, x):
            ctx.progress(50, "half")
            return x * 2
        tid = self.svc.submit(work, 21)
        ev = _wait(self.svc, lambda e: any(i.kind is EventKind.RESULT for i in e))
        kinds = [e.kind for e in ev if e.task_id == tid]
        self.assertEqual(kinds, [EventKind.PROGRESS, EventKind.RESULT])
        self.assertEqual(ev[-1].payload, 42)

    def test_error_is_delivered(self):
        def boom(ctx):
            raise ValueError("bad")
        self.svc.submit(boom)
        ev = _wait(self.svc, lambda e: bool(e))
        self.assertEqual(ev[0].kind, EventKind.ERROR)
        self.assertEqual(ev[0].message, "bad")

    def test_cancellation(self):
        started = threading.Event()

        def loop(ctx):
            started.set()
            while True:
                ctx.raise_if_cancelled()
                time.sleep(0.01)
        tid = self.svc.submit(loop)
        started.wait(2)
        self.svc.cancel(tid)
        ev = _wait(self.svc, lambda e: bool(e))
        self.assertEqual(ev[0].kind, EventKind.CANCELLED)

    def test_handler_runs_on_polling_thread(self):
        seen = []
        self.svc.submit(lambda ctx: 1, on_event=lambda e: seen.append(threading.current_thread()))
        _wait(self.svc, lambda e: bool(seen))
        self.assertIs(seen[0], threading.current_thread())


if __name__ == "__main__":
    unittest.main()
