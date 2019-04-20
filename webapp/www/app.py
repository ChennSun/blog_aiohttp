 #!/usr/bin/env python3
# -*- coding:utf-8 -*-

__author__="sunchen"
"""
async web application
"""
import logging; logging.basicConfig(level=logging.INFO,format='%(asctime)s-%(levelname)s-%(message)s')
import asyncio,os,json,time,orm
from datetime import datetime
from aiohttp import web
from coroweb import add_routes,add_static
from jinja2 import Environment,FileSystemLoader
from config import configs
from handlers import cookie2user,COOKIE_NAME


def init_jinja2(app,**kw):
	logging.info("init jinja2...")
	options=dict(
	autoescape=kw.get("autoescape",True),
	block_start_string=kw.get("block_start_string","{%"),
	block_end_string=kw.get("block_end_string","%}"),
	variable_start_string=kw.get("variable_start_string","{{"),
	variable_end_string=kw.get("variable_end_string","}}"),
	auto_reload=kw.get("auto_reload",True)
	)
	path=kw.get("path",None)
	if path==None:
		path=os.path.join(os.path.dirname(os.path.abspath(__file__)),"templates")
	logging.info("set jinja2 template path:%s"%path)
	env=Environment(loader=FileSystemLoader(path),**options)
	filters=kw.get("filters",None)#过滤器
	if filters:
		for name,f in filters.items():
			env.filters[name]=f
	app["__templating__"]=env
def datetime_filter(t):
	delta=int(time.time()-t)
	if delta < 60:
		return u"一分钟前"
	if delta < 3600: 
		return u"%s分钟前"%(delta//60)
	if delta < 86400:
		return u"%s小时前"%(delta//3600)
	if delta < 604800:
		return u"%s天前"%(delta//86400)
	dt=datetime.fromtimestamp(t)
	return u"%s年%s月%s日"%(dt.year,dt.month,dt.day)
@asyncio.coroutine
def logger_factory(app,handler):#handler= RequsetHandler(app,fn)()存疑
	@asyncio.coroutine
	def logger(request):
		logging.info("request :%s,%s"%(request.method,request.path))
		return (yield from handler(request))
	return logger
@asyncio.coroutine
def data_factory(app,handler):
	@anyncio.coroutine
	def parse_data(request):
		if request.method == "POST":
			if request.content_type.startswith('application/json'):
				request.__data__=yield from request.json()
				logging.info("request json :%s"%str(request.__data__))
			elif request.content_type.startswith("application/x-www-form-urlencoded"):
				request.__data__=yield from request.post()
				logging.info("request form :%s"%request.__data__)
			return (yield from handler(request))#相当于函数调用，主要执行工作位于RequestHandler中
	return parse_data
@asyncio.coroutine
def auth_factory(app,handler):
	@asyncio.coroutine
	def auth(request):
		logging.info("check user:%s,%s"%(request.method,request.path))
		request.__user__=None
		cookie_str=request.cookies.get(COOKIE_NAME)
		if cookie_str:
			user=yield from cookie2user(cookie_str)
			if user:
				logging.info("set current user:%s"%user.email)
				request.__user__=user
		if request.path.startswith("/manage/") and (request.__user__ is None or not request.__user__.admin):
			return web.HTTPFound("/signin")#非管理员不可执行manage操作。
		return (yield from handler(request))
	return auth
@asyncio.coroutine
def response_factory(app,handler):
	@asyncio.coroutine
	def response(request):
		logging.info("response handle...")
		r=yield from handler(request)
		if isinstance(r,web.StreamResponse):
			return r
		if isinstance(r,bytes):
			resp=web.Response(body=r)
			resp.content_type="application/octet-stream"
			return resp
		if isinstance(r,str):
			if r.startswith("redirect:"):#重定向字符串
				return web.HTTPFound(r[9:])#重定向至目标url
			resp = web.Response(body=r.encode("utf-8"))
			resp.content_type = "text/html;charset = utf-8"
			return resp
		if isinstance(r,dict):
			template=r.get("__template__")
			if template is None:
				resp=web.Response(body=json.dumps(r,ensure_ascii=False,default=lambda obj:obj.__dict__).encode("utf-8"))
				resp.content_type = "application/json;charset = utf-8"
				return resp
			else:
				r['__user__'] = request.__user__#缺少这句将无法显示登录状态
				resp = web.Response(body=app["__templating__"].get_template(template).render(**r).encode("utf-8"))
				resp.content_type="text/html;charset=utf-8"
				return resp
		if isinstance(r,int) and r>=100 and r<600:
			return web.Response(r)  
		if isinstance(r,tuple) and len(r) == 2:
			t,m = r
			if isinstance(t,int) and t>=100 and t<600:
				return web.Response(t,str(m))
		#default
		resp = web.Response(body=str(r).encode("utf-8"))
		resp.content_type="text/html;charset=utf-8"
		return resp
	return response

@asyncio.coroutine
def init(loop):
	#yield from orm.create_pool(loop=loop,host=configs.db.host,port=configs.db.port,user=configs.db.user,password=configs.db.password,db=configs.db.db)
	yield from orm.create_pool(loop=loop,**configs.db)#上面那种方式有点蠢
	app=web.Application(loop=loop,middlewares=[logger_factory,auth_factory,response_factory])
	init_jinja2(app,filters=dict(datetime=datetime_filter))
	add_routes(app,"handlers")
	add_static(app)
	srv = yield from loop.create_server(app.make_handler(),"localhost",9000)
	logging.info("server started at localhost:9000")
	#url与url处理函数之间的对应是通过aiohttp框架实现的。
loop=asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()
