#  Copyright 2008-2009 Nokia Siemens Networks Oyj
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import time

from robot import utils
from robot.utils.robotthread import Thread, Runner, Event
from robot.errors import TimeoutError, DataError, FrameworkError

from signalhandler import STOP_SIGNAL_MONITOR


class _Timeout:

    def __init__(self, timeout=None, message=''):
        self.string = timeout or ''
        self.message = message
        self.secs = -1
        self.starttime = 0
        self.error = None

    def replace_variables(self, variables):
        try:
            self.string = variables.replace_string(self.string)
            if not self.string:
                return
            self.secs = utils.timestr_to_secs(self.string)
            self.message = variables.replace_string(self.message)
        except DataError, err:
            self.secs = 0.000001 # to make timeout active
            self.error = 'Setting %s timeout failed: %s' % (self.type, unicode(err))

    def start(self):
        self.starttime = time.time()

    def time_left(self):
        if self.starttime == 0:
            raise FrameworkError('Timeout not started')
        elapsed = time.time() - self.starttime
        return self.secs - elapsed

    def active(self):
        return self.secs > 0

    def timed_out(self):
        return self.active() and self.time_left() < 0

    def __str__(self):
        return self.string

    def __cmp__(self, other):
        if utils.is_str(other):
            return cmp(str(self), other)
        if not self.active():
            return 1
        if not other.active():
            return -1
        return cmp(self.time_left(), other.time_left())

    def run(self, runnable, args=None, kwargs=None, logger=None):
        if self.error is not None:
            raise DataError(self.error)
        if not self.active():
            raise FrameworkError('Timeout is not active')
        timeout = self.time_left()
        STOP_SIGNAL_MONITOR.stop_running_keyword()
        if logger:
            logger.debug('%s timeout %s active. %s seconds left.'
                         % (self.type.capitalize(), self.string, round(timeout, 3)))
        STOP_SIGNAL_MONITOR.start_running_keyword()
        if timeout <= 0:
            raise TimeoutError(self.get_message())
        notifier = Event()
        runner = Runner(runnable, args, kwargs, notifier)
        # Thread's name is important - it's used in utils.outputcapture
        thread = Thread(runner, stoppable=True, daemon=True, name='TIMED_RUN')
        thread.start()
        time.sleep(0.001)
        notifier.wait(timeout)
        if runner.is_done():
            return runner.get_result()
        try:
            thread.stop()
        except utils.RERAISED_EXCEPTIONS:
            raise
        except:
            pass
        raise TimeoutError(self.get_message())

    def get_message(self):
        if self.message is not None:
            return self.message
        return '%s timeout %s exceeded.' % (self.type.capitalize(), self.string)


class TestTimeout(_Timeout):
    type = 'test'
    _kw_timeout_occurred = False

    def set_keyword_timeout(self, timeout_occurred):
        if not self._kw_timeout_occurred:
            self._kw_timeout_occurred = timeout_occurred

    def any_timeout_occurred(self):
        return self.timed_out() or self._kw_timeout_occurred


class KeywordTimeout(_Timeout):
    type = 'keyword'
