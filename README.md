# PTB

Post Transmitter Bot or PTB for short is a Telegram bot
which can be used to create mirrors of VK groups as 
Telegram channels.

## Commands
`/get <vk_group_id> <short_group_adress> [offset=0]` &mdash;
get post from group with id `vk_group_id` and short adress `short_group_adress`.
`offset` specifies post index starting from the most recent post.

## Run
### Using docker

### Without container 
You will need to create setting.env file with variables 
shown in test.env.tpl or load environment variables manually.
```
    python3 -m venv ptb-venv
    source ptb-venv/bin/activate 
    pip3 install -r requirements.txt
    python3 bot.py --load settings.env
```

## Usage
To run bot as a mirror you can use `--mirror` option. 
To see all options and their usage use `-h` option.
