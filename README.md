# PTB

Post Transmitter Bot or PTB for short is a Telegram bot
which can be used to create mirrors of VK groups as 
Telegram channels.

## Commands
`/get <vk_group_id> <short_group_adress> [offset=0]` &mdash;
get post from group with id `vk_group_id` and short adress `short_group_adress`.
`offset` specifies post index starting from the most recent post.

## Run
You will need to create settings.env file with variables 
shown in test.env.tpl or load environment variables manually.
To run without DB and commands which need it you can 
omit `--mirror` option.

### Using docker
If you have Postgres database somewhere, you can fill settings.env accordingly and run:
```
sudo docker run --env ENV_VARS="$(cat ./settings.env)" -it ptb:0.2 bash -c "./entrypoint.sh --mirror"
```
If you want to run bot and db in containers on the same network you can use docker-compose. 
Before running command below you should specify name of your `.env` settings file inside 
docker-compose.yaml. It is `test.env` by default.
```
sudo docker compose up -d
```

### Without container 
```
python3 -m venv ptb-venv
source ptb-venv/bin/activate 
pip3 install -r requirements.txt
python3 bot.py --load settings.env --mirror
```

To run db you can use:
```
docker run --name pdb_db -p 6644:5432 -e POSTGRES_USER=admin -e POSTGRES_PASSWORD=password -e POSTGRES_DB=ptb_db -e PGDATA=/var/lib/postgresql/data/pgdata -v "ptb_db_data:/var/lib/postgresql/data" -d postgres:13.3
```

## Usage
To see all options and their usage use `-h` option.
To see all bot's commands send him `/help` message.
