import inspect
from collections import defaultdict
from functools import partial
from typing import Callable

class Bus:
    _event_map = dict()

    @staticmethod
    def on(event: str, callback: Callable, *args, **kwargs):
        cb = partial(callback, *args, **kwargs)
        Bus._event_map.setdefault(event, [])
        Bus._event_map[event].append(cb)
        print(f"Registered for {event}")

    @staticmethod
    def emit(event: str, **kwargs):
        fns = Bus._event_map.get(event)
        if not fns:
            print(f"WARN: Emitted {event} but no one cares")
            return
        for cb in fns:
            cb(**kwargs)
