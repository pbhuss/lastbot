from typing import Union, List

from lastbot.util import get_redis


def set_lastfm_user(team_id: str, user_id: str) -> int:
    redis = get_redis()
    redis.sadd('teams', team_id)
    return redis.hset(f'users:{team_id}', user_id)


def get_lastfm_user(team_id: str, user_id: str) -> Union[str, None]:
    return get_redis().hget(f'users:{team_id}', user_id)


def get_teams():
    return get_redis().smembers('teams')


def get_user_map(team_id: str) -> Union[dict, None]:
    return get_redis().hgetall(f'users:{team_id}')
