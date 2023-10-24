import json
import pathlib

import natsort
import quart
import random, yaml
from functools import lru_cache

app = quart.Quart('app')

cfg = pathlib.Path("Config.yaml")
if cfg.exists():
    with open(cfg,encoding="utf-8") as f:
        e = yaml.safe_load(f)
else:
    e = {}
conf = e
fs = conf.setdefault('work-path',None)

if fs:
    fs = pathlib.Path(fs)

dirs = [i for i in list(fs.iterdir()) if i.is_dir()]

token = random.randint(1000,9999)

print("========== TOKEN ==========")
print("Token for today is: ", token)
print("========== TOKEN ==========")

@app.route('/static_fs/<string:author>/<path:router>')
async def static_fs(author, router):
    
    if author in [i.name for i in dirs]:
        img = fs / author / router
        #print(img)
        if img.exists():
            return await quart.send_file(img)


@lru_cache(maxsize=100, typed=True)
def construct_posts(author: pathlib.Path):
    author_posts = {}
    for post in author.iterdir():
        author_posts[post.name] = []
        if post.stem.startswith("_"):
            print("Detected loose folder.")
            for folder in post.iterdir():
                author_posts[folder.name] = []
                for file in folder.iterdir():
                    if file.suffix.lower().endswith('jpg') or file.suffix.lower().endswith('png') or \
                        file.suffix.lower().endswith('jpeg') or file.suffix.lower().endswith('gif'):
                        author_posts[folder.name].append(file.relative_to(fs).as_posix())
        else:
            if post.is_dir():
                for file in post.iterdir():
                    if file.suffix.lower().endswith('jpg') or file.suffix.lower().endswith('png') or \
                            file.suffix.lower().endswith('jpeg') or file.suffix.lower().endswith('gif'):
                        #print(file.relative_to(fs).as_posix())
                        author_posts[post.name].append(file.relative_to(fs).as_posix())
    sorted = natsort.os_sorted(author_posts, reverse=True)
    a = {}
    for s_key in sorted:
        a[s_key] = author_posts[s_key]
    return a

@app.route('/author/all')
async def author_route_all():
    print("special")
    pp = {}
    for author in dirs:
        posts_data = construct_posts(fs / author.name)
        pp.update(posts_data)
    sorted = natsort.os_sorted(pp, reverse=True)
    a = {}
    for s_key in sorted:
        a[s_key] = pp[s_key]
    
    return await quart.render_template('author.html', posts=pp, author="")


@app.route('/author/<string:author>')
async def author_route(author):
    if author in [i.name for i in dirs]:
        posts_data = construct_posts(fs / author)
    else:
        raise Exception
    print(posts_data)
    return await quart.render_template('author.html', posts=posts_data, author=author)


@app.route('/',methods=['get','post'])
async def root():
    if quart.request.method == "POST":
        a = quart.redirect('/')
        f = await quart.request.form
        a.set_cookie('tk',f['token'])
        return a
    tk = quart.request.cookies.get('tk',default='0')
    tk = int(tk)
    if tk != token:
        return await quart.render_template('root_token.html')
    
    return await quart.render_template('root.html', dirs=dirs)


if __name__ == '__main__':
    app.run("0.0.0.0", port=80, debug=False)
