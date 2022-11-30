# https://redis.io/topics/quickstart

wget http://download.redis.io/redis-stable.tar.gz
tar xvzf redis-stable.tar.gz
cd redis-stable
make
sudo make install

## Install properly
sudo mkdir /etc/redis
sudo mkdir /var/redis
sudo cp utils/redis_init_script /etc/init.d/redis_6379

## Optionally edit config to suite you needs
sudo nano /etc/init.d/redis_6379

sudo cp redis.conf /etc/redis/6379.conf

## Edit config 
sudo nano /etc/redis/6379.conf

sudo update-rc.d redis_6379 defaults
sudo /etc/init.d/redis_6379 start
