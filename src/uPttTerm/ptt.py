import time

import PyPtt


class UPttService:
    def __init__(self):
        self.service: PyPtt.Service = PyPtt.Service(
            # {'log_level': PyPtt.log.SILENT}
        )
        self.ptt_id = None
        self.ptt_pw = None

        self.max_retry = 3
        self.retry_delay = 2  # seconds

    def login(self, ptt_id: str, ptt_pw: str, force: bool = True):

        self.service.call('login', {'ptt_id': ptt_id, 'ptt_pw': ptt_pw, 'kick_other_session': force})

        # store while login successfully
        self.ptt_id = ptt_id
        self.ptt_pw = ptt_pw

    def call(self, api, args=None):

        if self.ptt_pw is None or self.ptt_id is None:
            raise PyPtt.RequireLogin("Please login first before calling any API.")

        for _ in range(self.max_retry):
            try:
                return self.service.call(api, args)
            except PyPtt.ConnectionClosed:
                time.sleep(self.retry_delay)
                self.service.call(
                    'login',
                    {'ptt_id': self.ptt_id, 'ptt_pw': self.ptt_pw, 'kick_other_session': True})
        return None

    def close(self):
        self.service.call('logout')
        self.service.close()
