from collections import defaultdict
from threading import Thread
from queue import Queue, Empty

from common.logging_utils import get_logger

logger = get_logger(__name__)


class Event:
    def __init__(self, event_type, data=None):
        self.event_type = event_type
        self.data = data


class EventEngine:
    def __init__(self):
        self.__queue = Queue()
        self.__active = False
        self.__thread = Thread(target=self.__run, name="EventEngine.__thread")
        self.handlers = defaultdict(list)

    def __run(self):
        while self.__active:
            try:
                event = self.__queue.get(block=True, timeout=1)
                handle_thread = Thread(
                    target=self.__process, args=(event,), name="EventEngine.__process"
                )
                handle_thread.start()
            except Empty:
                pass

    def __process(self, event):
        if event.event_type in self.handlers:
            logger.debug("处理事件 %s（%d 个处理器）", event.event_type, len(self.handlers[event.event_type]))
            for handler in self.handlers[event.event_type]:
                handler(event)

    def start(self):
        self.__active = True
        self.__thread.start()
        logger.info("事件引擎已启动")

    def stop(self):
        self.__active = False
        self.__thread.join()
        logger.info("事件引擎已停止")

    def register(self, event_type, handler):
        if handler not in self.handlers[event_type]:
            self.handlers[event_type].append(handler)
            logger.debug("注册事件处理器 %s", event_type)

    def unregister(self, event_type, handler):
        handler_list = self.handlers.get(event_type)
        if handler_list is None:
            return
        if handler in handler_list:
            handler_list.remove(handler)
        if len(handler_list) == 0:
            del self.handlers[event_type]

    def put(self, event):
        self.__queue.put(event)
        logger.debug("入队事件 %s（队列大小 %d）", event.event_type, self.__queue.qsize())

    def queue_size(self):
        return self.__queue.qsize()
