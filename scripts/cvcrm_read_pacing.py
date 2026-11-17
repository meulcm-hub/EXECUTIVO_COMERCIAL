"""CVDW permite 20 consultas/minuto: fila única, com margem e pausa global 429."""
import email.utils
import time
import datetime as dt

class ReadPacer:
    def __init__(self, interval=4.2, clock=None, sleep=None):
        self.interval=interval
        self.clock=clock or time.monotonic
        self.sleep=sleep or time.sleep
        self.next_at=0
    def wait(self):
        delay=self.next_at-self.clock()
        if delay>0:self.sleep(delay)
        self.next_at=self.clock()+self.interval
    def cooldown(self,seconds):
        self.next_at=max(self.next_at,self.clock()+seconds)

def retry_after(headers,now=None):
    """O CV bloqueia por um minuto. Nunca repetir antes de 65s ou Retry-After."""
    value=(headers or {}).get('Retry-After','')
    try:return max(65,float(value))
    except (ValueError,TypeError):pass
    try:
        until=email.utils.parsedate_to_datetime(value)
        now=now or dt.datetime.now(dt.timezone.utc)
        return max(65,(until-now).total_seconds())
    except (ValueError,TypeError,OverflowError):return 65

PACER=ReadPacer()
