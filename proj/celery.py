from datetime import timedelta

from celery import Celery

app = Celery(
    "proj",
    broker="amqp://user:password@localhost:5672/my_vhost",
    include=['proj.tasks']
)

app.conf.beat_schedule = {
    'update_rates': {
        'task': 'proj.tasks.update_rates',
        'schedule': timedelta(seconds=60),
    },
    'update_balances': {
        'task': 'proj.tasks.update_balances',
        'schedule': timedelta(seconds=60),
    },

}
app.conf.update(task_track_started=True)

if __name__ == '__main__':
    app.start()
