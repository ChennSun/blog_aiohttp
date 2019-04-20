#!usr/bin/env python3
# -*- coding:utf-8 -*-
from coroweb import post,get
import asyncio,logging,json,time,re,hashlib,base64,config
import markdown2
from aiohttp import web
from config import configs
from models import User,Comment,Blog,next_id
from apis import APIError,APIValueError,Page,APIPermissionError,APIResourceNotFoundError

COOKIE_NAME = "awesession"
_COOKIE_KEY = configs.session.secret

def check_admin(request):
	if request.__user__ is None or not request.__user__.admin:
		raise APIPermissionError()
def get_page_index(page_str):
	p=1
	try:
		p = int(page_str)
	except ValueError as e:
		pass
	if p<1:
		p=1
	return p

def text2html(text):
	lines = map(lambda s:"<p>%s</p>"%s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt"),filter(lambda s:s.strip()!="",text.split("\n")))#map(lambda,filter)
	return ' '.join(lines)

def user2cookie(user,max_age):
	expires=str(int(time.time()+max_age))
	s="%s-%s-%s-%s"%(user.id,user.passwd,expires,_COOKIE_KEY)
	L=[user.id,expires,hashlib.sha1(s.encode("utf-8")).hexdigest()]
	return "-".join(L)

@asyncio.coroutine
def cookie2user(cookie_str):
	if not cookie_str:
		return None
	try:
		L=cookie_str.split("-")
		if len(L)!=3:
			return None
		uid,expires,sha1=L
		if int(expires)<time.time():
			return None
		user=yield from User.find(uid)
		s="%s-%s-%s-%s"%(uid,user.passwd,expires,_COOKIE_KEY)
		if sha1 !=hashlib.sha1(s.encode("utf-8")).hexdigest():
			logging.info("invalid sha1")
			return None
		user.passwd="*********"
		return user
	except Exception as e:
		logging.exception(e)
		return None
"""
@get('/')
def index(request):
	summary='Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
	blogs = [
		Blog(id='1', name='Test Blog', summary=summary, created_at=time.time()-120),
		Blog(id='2', name='Something New', summary=summary, created_at=time.time()-3600),
		Blog(id='3', name='Learn Swift', summary=summary, created_at=time.time()-7200)
	]
	return {
		'__template__':'blogs.html',
		'blogs': blogs#传入模板参数要和模板内｛{xxx}｝中的参数名一一对应.传入模板的参数为__template__=blogs.html以及blogs列表，模板中采用for循环获取blogs列表中的类(blog=Blog(xxxx))
	}
"""
@get("/")
def index(*,page="1"):
	page_index = get_page_index(page)
	num = yield from Blog.findNumber("count(id)")
	page=Page(num)
	if num == 0:
		blogs=[]
	else:
		blogs = yield from Blog.findAll(orderBy="created_at desc",limit=(page.offset,page.limit))
	return{
	"__template__":"blogs.html",
	"page":page,
	"blogs":blogs
	}

@get("/register")
def register():
	return {
	"__template__":"register.html"
	}

@get("/signin")
def signin():
	return{
	"__template__":"signin.html"
	}

@get("/signout")
def signout(request):
	referer = request.headers.get("Referer")
	r=web.HTTPFound(referer or "/")
	r.set_cookie(COOKIE_NAME,"-deleted-",max_age=0,httponly=True)
	logging.info("user signed out")
	return r

_RE_EMAIL=re.compile(r"^[a-z0-9\-\_\.]+\@[a-z0-9\_\-]+(\.[a-z0-9\_\-]+){1,4}$")
_RE_SHA1=re.compile(r"^[0-9a-f]{40}$")

@post("/api/users")#用户注册
def api_register_user(*,email,name,passwd):
	if not name or not name.strip():
		raise APIValueError("name")
	if not email or not _RE_EMAIL.match(email):
		raise APIValueError("email")
	if not passwd or not _RE_SHA1.match(passwd):
		raise APIValueError("passwd")
	users = yield from User.findAll("email=?",[email])
	if len(users)>0:
		raise APIError("register:failed","email","Email is already in use")
	uid=next_id()
	sha1_passwd="%s:%s"%(uid,passwd)
	user=User(id=uid,name=name.strip(),email=email,passwd=hashlib.sha1(sha1_passwd.encode("utf-8")).hexdigest(),image="http://www.gravatar.com/avatar/%s?d=mm&s=120"%hashlib.md5(email.encode("utf-8")).hexdigest())
	yield from user.save()
	r=web.Response()#创建一个Response对象
	r.set_cookie(COOKIE_NAME,user2cookie(user,86400),max_age=86400,httponly=True)#set_cookie为web.Response对象的一个方法，创建该方法后方可使用。
	user.passwd="********"
	r.content_type="application/json"
	r.body=json.dumps(user,ensure_ascii=False).encode("utf-8")
	return r

@post("/api/authenticate")#账号登录时的检查及生成cookie
def authenticate(*,email,passwd):
	if not email:
		raise APIValueError("email","Invalid email")
	if not passwd:
		raise APIValueError("passwd","Invalid email")
	users=yield from User.findAll("email=?",[email])
	if len(users)==0:
		raise APIValueError("email","Email not exist")
	user=users[0]
	sha1=hashlib.sha1()
	sha1.update(user.id.encode("utf-8"))
	sha1.update(b":")
	sha1.update(passwd.encode("utf-8"))
	if user.passwd != sha1.hexdigest():
		raise APIValueError("passwd","Invalid passwd")
	r=web.Response()
	r.set_cookie(COOKIE_NAME,user2cookie(user,86400),max_age=86400,httponly=True)
	user.passwd="********"
	r.content_type="application/json"
	r.body=json.dumps(user,ensure_ascii=False).encode("utf-8")
	return r

@get("/api/users")
def api_get_users():
	users = yield from User.findAll(orderBy="created_at desc")
	for u in users:
		u.passwd="*********"
	return dict(users=users)

@get("/blog/{id}")#打开对应id的blog，简单点说就是打开一篇文章
def get_blog(id):
	blog = yield from Blog.find(id)
	comments = yield from Comment.findAll("blog_id=?",[id],orderBy="created_at desc")
	for c in comments:
		c.html_content = text2html(c.content)
	blog.html_content=markdown2.markdown(blog.content)
	return {
	"__template__":"blog.html",
	"blog":blog,
	"comments":comments#模板内无comment传入位置，存疑
	}

@get("/manage/blogs")#管理员管理博客列表
def manage_blogs(*,page='1'):#page为什么不直接传入int型？
	return {
	"__template__":"manage_blogs.html",
	"page_index":get_page_index(page)
	}

@get("/manage/blogs/create")#编辑一篇新日志
def manage_create_blog():
	return{
	"__template__":"manage_blog_edit.html",
	"id":'',
	"action":"api/blogs"
	}

@get("/manage/blogs/edit")
def manage_edit_blog(*,id):
	return {
	"__template__":"manage_blog_edit.html",
	"id":id,
	"action":"/api/blogs/%s"%id
	}

@post("/api/blogs/{id}")
def api_update_blog(id,request,*,name,summary,content):
	check_admin(request)
	blog = yield from Blog.find(id)
	if not name or not name.strip():
		raise APIValueError("name","name cannot be empty.")
	if not summary or not summary.strip():
		raise APIValueError("summary","summary cannot be empty.")
	if not content or not content.strip():
		raise APIValueError("content","content cannot be empty.")
	blog.name=name.strip()
	blog.summary=summary.strip()
	blog.content=content.strip()
	yield from blog.update()
	return blog

@get("/api/blogs")#获取日志列表
def api_blogs(*,page="1"):
	page_index = get_page_index(page)
	num = yield from Blog.findNumber("count(id)")
	p=Page(num,page_index)
	if num==0:
		return dict(page=p,blogs=())
	blogs = yield from Blog.findAll(orderBy="created_at desc",limit=(p.offset,p.limit))
	return dict(page=p,blogs=blogs)

@get("/api/blogs/{id}")
def api_get_blog(*,id):
	blog=yield from Blog.find(id)
	return blog

@post("/api/blogs")#保存blog
def api_create_blog(request,*,name,summary,comment):
	check_admin(request)
	if not name or not name.strip():
		raise APIValueError("name","name cannot be empty")
	if not summary or not summary.strip():
		raise APIValueError("summary","summary cannot be empty")
	if not content or not content.strip():
		raise APIValueError("content","content cannot be empty")
	blog=Blog(user_id=request.__user__.id,user_name=request.__user__.name,user_image=requset.__user__.image,name=name.strip(),summary=summary.strip(),content=content.strip())
	yield from blog.save()
	return blog

@get("/manage/")
def manage():
	return "redirect:/manage/comments"

@get("/manage/comments")
def manage_comment(*,page="1"): 
	return {
	"__template__":"manage_comments.html",
	"page_index":get_page_index(page)
	}

@get('/manage/users')
def manage_users(*, page='1'):
	return {
		'__template__': 'manage_users.html',
		'page_index': get_page_index(page)
	}

@post("/api/blogs/{id}/delete")
def api_delete_blog(request,*,id):
	check_admin(request)
	blog = yield from Blog.find(id)
	yield from blog.remove()
	return dict(id=id)

@get("/api/comments")
def api_comments(*,page="1"):
	page_index = get_page_index(page)
	num = yield from Comment.findNumber("count(id)")
	p=Page(num,page_index)
	if num == 0:
		return dict(page=p,comments=())
	comments = yield from Comment.findAll(orderBy="created_at desc",limit=(p.offset,p.limit))
	return dict(page=p,comments=comments)

@post("/api/blogs/{id}/comments")
def api_create_comment(id,request,*,content):
	user=request.__user__
	if user == None:
		raise APIPermissionError("please signin first")
	if not content or not content.strip():
		raise APIValueError("content")
	blog = yield from Blog.find(id)
	if blog is None:
		raise APIResourceNotFoundError("Blog")
	comment = Comment(blog_id=blog.id,user_id=user.id,user_name=user.name,user_image=user.image,content=content.strip())
	yield from comment.save()
	return comment

@post("/api/comments/{id}/delete")
def api_delete_comments(id,request):
	check_admin(request)
	c=yield from Comment.find(id)
	if c is None:
		raise APIResourceNotFoundError("Comment")
	yield from c.remove()
	return dict(id=id)