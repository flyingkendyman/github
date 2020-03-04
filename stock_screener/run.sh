#!/bin/bash

printenv > /etc/default/locale
service cron start
echo 'Smartie is ready for action!'
ln -sf /proc/1/fd/1 /var/log/cron.log
echo '*/5 * * * * root cd / && /opt/conda/envs/stock_screener/bin/python ./app.py >> /var/log/cron.log' > /etc/crontab
tail -f /var/log/cron.log
