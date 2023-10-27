import asyncio
import pathlib
import random

import httpx
import orjson
import tqdm
import yaml

cfg = pathlib.Path("Config.yaml")
if cfg.exists():
    with open(cfg, encoding="utf-8") as f:
        e = yaml.safe_load(f)
else:
    e = {}
conf = e
work_path = conf.setdefault("work-path", None)
users = conf.setdefault("users", ["!placeholder", "!placeholder"])

if not work_path:
    cfg.write_text(yaml.dump(e), encoding="utf-8")
    raise Exception("Work path missing")

if not users or users[0] == "!placeholder":
    cfg.write_text(yaml.dump(e), encoding="utf-8")
    raise Exception("fill in users please")
else:
    print(f"Scraping users: {users}")

if conf.get("cookie") is None:
    cfg.write_text(yaml.dump(e), encoding="utf-8")
    raise Exception("Missing cookies.")
else:
    cookie = conf.get("cookie")
    if not cookie:
        raise Exception("Missing cookies.")

work_path = pathlib.Path(work_path).resolve()
if not work_path.is_dir():
    work_path.mkdir(exist_ok=True, parents=True)


def body2mark(real_body):
    
    body = real_body.get("body")
    content = {}
    md = body.get("blocks", [])
    if body.get("blocks"):
        fileMap = body.get("fileMap")
        imageMap = body.get("imageMap")
        content["file"] = fileMap
        content["image"] = imageMap
    else:
        fileMap = body.get("files", [])
        imageMap = body.get("images", [])
        # plain txt & images...
        content["file"] = fileMap
        content["image"] = imageMap
    content["blocks"] = md
    content["creator"] = real_body.get("creatorId")
    content["title"] = real_body.get("title")
    content["post_id"] = real_body.get("id")
    return content


async def main():
    async_session = httpx.AsyncClient()
    async_session.cookies.set("FANBOXSESSID",cookie,"fanbox.cc")
    async_session.headers["user-agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36"
    async_session.headers["accept"] = "application/json"
    async_session.headers["origin"] = "https://www.fanbox.cc"

    cfg.write_text(yaml.dump(e), encoding="utf-8")
    # Open the indexer
    if (work_path / "index_new.json").exists():
        with open((work_path / "index_new.json"), "r", encoding="utf-8") as f:
            indexes = orjson.loads(f.read())
    else:
        indexes = {}

    running_set = set(list(indexes.keys()))

    auto_magic = "~auto"
    selected_users = set()
    for user in users:
        if user == auto_magic:
            resp = await async_session.get(f"https://api.fanbox.cc/plan.listSupporting")
            if resp.status_code != 200:
                raise Exception(f"Unexpected error: {resp.status_code}")
            j_data = resp.json()
            # users.clear()
            for creator in j_data["body"]:
                print(f"[auto] Adding: {creator['creatorId']}")
                selected_users.add(creator["creatorId"])
        else:
            print(f"[Manual] Adding: {user}")
            selected_users.add(user)
    
        

    posts = []
    max_inflight = asyncio.Semaphore(10)
    pbar = tqdm.tqdm(total=0)

    async def page_task(page: str, creator_name):
        async with max_inflight:
            while True:
                response = await async_session.get(page)
                if response.status_code != 200:
                    await asyncio.sleep(random.uniform(0, 1))
                    continue
                j_data = response.json()
                has_post = False
                for post in j_data.get("body",{"items":[]})["items"]:
                    has_post = True
                    if (
                        post["isRestricted"]
                        and post["id"] not in running_set
                    ):
                        print(
                            f"Skipping post @{creator_name}/{post['id']} as it was not unlocked."
                        )
                        continue
                    if post["id"] in running_set:
                        continue
                    posts.append(post["id"])
                if not has_post:
                    print(f"Unknown response from. Got {j_data}")
                    await asyncio.sleep(random.uniform(0, 5))
                else:
                    pbar.update(1)
                    break
                # 
                        

    for creator in selected_users:
        pages = await async_session.get(
            f"https://api.fanbox.cc/post.paginateCreator?creatorId={creator}"
        )
        if pages.status_code == 200:
            j_data = pages.json()
            for pagination in j_data["body"]:
                pbar.total += 1
                await page_task(pagination, creator)

    async def grb(pp_id):
        async with max_inflight:
            await asyncio.sleep(random.uniform(0.5, 1))
            while True:
                try:
                    r = await async_session.get(
                        f"https://api.fanbox.cc/post.info?postId={pp_id}"
                    )
                    rj = r.json()
                    parsed = body2mark(rj.get("body"))
                    # print(parsed)
                    indexes[parsed["post_id"]] = parsed
                    print(f"Indexed post: {parsed['post_id']}")
                    break
                except httpx.NetworkError:
                    await asyncio.sleep(random.uniform(0.5, 1))
                    continue
                except httpx.ProtocolError:
                    await asyncio.sleep(random.uniform(0.5, 1))
                    continue

    tsks = [asyncio.create_task(grb(p_id)) for p_id in posts]
    await asyncio.gather(*tsks)

    with open((work_path / "index_new.json"), "wb") as f:
        f.write(orjson.dumps(indexes, option=orjson.OPT_INDENT_2))


if __name__ == "__main__":
    print("Indexing...")
    asyncio.run(main())
