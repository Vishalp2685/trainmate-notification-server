def extract_friend_ids(friends_data):
    ids = []
    for f in friends_data or []:
        if isinstance(f, dict):
            # adjust key if your column name differs
            ids.append(f.get("unique_id") or f.get("user_id"))
        elif isinstance(f, (list, tuple)):
            ids.append(f[0])
        else:
            ids.append(f)
    return ids
