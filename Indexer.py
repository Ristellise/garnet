import asyncio
import pathlib
import random

import aiohttp
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

work_path = pathlib.Path(work_path).resolve()
if not work_path.is_dir():
    work_path.mkdir(exist_ok=True, parents=True)


def body2mark(real_body):
    md = ""
    body = real_body.get("body")
    content = {}
    if body.get("blocks"):

        fileMap = body.get("fileMap")
        imageMap = body.get("imageMap")

        for block in body.get("blocks"):
            b_type = block["type"]
            if b_type == "p":
                styls = block.get(
                    "styles"
                )  # TODO: Figure out styles once I have a sample of some reallt weird styling.
                if styls:
                    pass
                    md += f"{b_type}  \n"
                    # print("Found styled text, ignoring for now.")
                else:
                    text = block.get("text")
                    md += f"{text}  \n"
            elif b_type == "image":
                im = imageMap[block["imageId"]]
                md += f"![]({im['id']}.{im['extension']} \"{im['id']}\")  \n"
            elif b_type == "file":
                file = fileMap[block["fileId"]]
                md += f"[File: {file['name']}]({file['id']}.{file['extension']} \"{file['id']}\")  \n"
        content["file"] = fileMap
        content["image"] = imageMap
    else:
        fileMap = body.get("files", [])
        imageMap = body.get("images", [])
        # plain txt & images...
        md += body.get("text", "").replace("\n", "  \n")
        content["file"] = fileMap
        content["image"] = imageMap
    content["markdown"] = md
    content["creator"] = real_body.get("creatorId")
    content["title"] = real_body.get("title")
    content["post_id"] = real_body.get("id")
    return content


async def main():

    async with aiohttp.ClientSession(cookies={"FANBOXSESSID": cookie}) as session:
        session.headers.update(
            {
                "user-agent": conf.setdefault(
                    "user-agent",
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36",
                ),
                "accept": "application/json",
                "origin": "https://www.fanbox.cc",
            }
        )
        # 'cookie': conf.setdefault('cookie',None),
        # session.cookie_jar.update_cookies(, yarl.URL("https://fanbox.cc"))

        cfg.write_text(yaml.dump(e), encoding="utf-8")
        # Open the indexer
        if (work_path / "index_new.json").exists():
            with open((work_path / "index_new.json"), "r", encoding="utf-8") as f:
                indexes = orjson.loads(f.read())
        else:
            indexes = {}

        running_set = set(list(indexes.keys()))

        if users[0] == "~auto":
            if len(users) != 1:
                raise Exception("!auto must be only defined once.")
            resp = await session.get(f"https://api.fanbox.cc/plan.listSupporting")
            if resp.status != 200:
                raise Exception(f"Unexpected error: {resp.status}")
            j_data = await resp.json()
            users.clear()
            for creator in j_data["body"]:
                print(f"[auto] Adding: {creator['creatorId']}")
                users.append(creator["creatorId"])

        posts = []
        sem = asyncio.Semaphore(5)
        # print(list(session.cookie_jar))
        pbar = tqdm.tqdm(total=0)

        async def page_task(page: str, page_c):
            async with sem:
                task_done = False
                while not task_done:
                    response = await session.get(page)
                    # print(list(response.cookies))
                    if response.status != 200:
                        await asyncio.sleep(random.uniform(0, 1))
                    else:
                        j_data = await response.json()
                        if j_data.get("body"):
                            for post in j_data.get("body")["items"]:
                                if (
                                    post["isRestricted"]
                                    and post["id"] not in running_set
                                ):
                                    # print(post)
                                    print(
                                        f"Post {post['id']} from {page_c} is not unlocked. Skipping..."
                                    )
                                    pbar.update(1)
                                    continue
                                if post["id"] in running_set:
                                    # print(
                                    #     f"Post {post['id']} from {page_c} already has been indexed."
                                    # )
                                    pbar.update(1)
                                    continue
                                posts.append(post["id"])
                            return
                        else:
                            print(f"Unknown response from. Got {j_data}")
                            await asyncio.sleep(random.uniform(0, 5))

        for creator in users:
            pages = await session.get(
                f"https://api.fanbox.cc/post.paginateCreator?creatorId={creator}"
            )
            if pages.status == 200:
                j_data = await pages.json()

                for pagination in j_data["body"]:
                    pbar.total += 1
                    await page_task(pagination, creator)

        async def grb(pp_id):
            async with sem:
                await asyncio.sleep(random.uniform(0.5, 1))
                while True:
                    try:
                        r = await session.get(
                            f"https://api.fanbox.cc/post.info?postId={pp_id}"
                        )
                        rj = await r.json()

                        parsed = body2mark(rj.get("body"))
                        # print(parsed)
                        indexes[parsed["post_id"]] = parsed
                        print(f"Indexed post: {parsed['post_id']}")
                        break
                    except aiohttp.ServerDisconnectedError:
                        await asyncio.sleep(random.uniform(0.5, 1))
                        continue

        tsks = [asyncio.create_task(grb(p_id)) for p_id in posts]
        await asyncio.gather(*tsks)

        with open((work_path / "index_new.json"), "wb") as f:
            f.write(orjson.dumps(indexes, option=orjson.OPT_INDENT_2))


if __name__ == "__main__":
    print("Indexing...")
    asyncio.run(main())
