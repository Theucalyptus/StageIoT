import queue
import logging

logger = logging.getLogger(__name__)

class Buffer:
    """
        Upload buffer. Wraps around a limited-size queue
        Automatically removes the oldest element when trying to add a new one in a full buffer. 
    """

    def __init__(self, size=1):
        """
            Creates a upload buffer (wrapper around a queue with auto-replacing)
        """
        self.queue = queue.Queue(1)

    def put(self, item):
        if self.queue.full():
            #logging.info("writing in non-empty buffer, reader may be too slow")
            try:
                self.queue.get_nowait()
            except queue.Empty:
                pass
        self.queue.put(item)

    def empty(self):
        return self.queue.empty()

    def get(self, block=True, timeout=0):
        """
            Get the data contained in the buffer.
            If timeout is set and no data is available, throws Empty exception.
        """
        return self.queue.get(block=block, timeout=timeout)