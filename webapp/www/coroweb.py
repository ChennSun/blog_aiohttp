#!/usr/bin/env python3
# -*- coding:utf-8 -*-

__author__="sun"
import functools,asyncio,os,logging,inspect
from urllib import parse
from aiohttp import web
from apis import APIError

def get(path):#为函数添加__method__及__route__属性
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = "GET"
        wrapper.__route__ = path
        return wrapper
    return decorator
def post(path):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = "POST"
        wrapper.__route__ = path
        return wrapper
    return decorator
def has_request_arg(fn):#fn参数中是否含有request参数，且其后不应再有其他位置参数。
    params = inspect.signature(fn).parameters
    found=False
    for name,param in params.items():
        if name=="request":
            found = True
            continue
        if found and (param.kind!=inspect.Parameter.VAR_KEYWORD and param.kind!=inspect.Parameter.VAR_POSITIONAL and param.kind!=inspect.Parameter.KEYWORD_ONLY):
            raise ValueError("request must be the last named parameter in function:%s%s"%(fn.__name__,str(sig)))
    return found
def has_var_kw_arg(fn):#fn参数中是否含有关键字参数，返回布尔值。
    params=inspect.signature(fn).parameters
    for name,param in params.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True
def has_named_kw_args(fn):#fn参数中是否含有命名关键字参数，返回布尔值。
    params = inspect.signature(fn).parameters
    for name, param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            return True
def get_named_kw_args(fn):#获取fn参数中的命名关键字参数，返回元组
    args=[]
    params=inspect.signature(fn).parameters
    for name,param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY:
            args.append(name)
    return tuple(args)
def get_required_kw_args(fn):#获取fn参数中的无默认值的命名关键字参数，返回元组。
    args=[]
    params=inspect.signature(fn).parameters
    for name,param in params.items():
        if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
            args.append(name)
    return tuple(args)

class RequestHandler(object):
    def __init__(self,app,fn):
        self._app=app
        self._func=fn
        self._has_request_arg=has_request_arg(fn)
        self._has_var_kw_args=has_var_kw_arg(fn)
        self._has_named_kw_args=has_named_kw_args(fn)
        self._named_kw_args=get_named_kw_args(fn)
        self._required_kw_args=get_required_kw_args(fn)
    @asyncio.coroutine
    def __call__(self, request):
        kw=None
        if self._has_var_kw_args or self._has_named_kw_args or self._required_kw_args:
            if request.method=="POST":
                if not request.content_type:
                    return web.HTTPBadRequest(text="Missing Content_Type")#貌似要加text
                ct=request.content_type.lower() #将大写字母转换为小写字母
                if ct.startswith("application/json"):#检测是否以指定字符串开头
                    params = yield from request.json()#获取JSON数据（存疑）
                    if not isinstance(params,dict):
                        return web.HTTPBadRequest(text="JSON body must be object")
                    kw=params
                elif ct.startswith("application/x-form-urlencoded") or ct.startswith("multipart/form-data"):
                    params=yield from request.post()
                    kw=dict(**params)#????????
                else:
                    return web.HTTPBadRequest("Unsopported Content_Type:%s"%request.content_type)
            if request.method=="GET":
                qs=request.query_string#request中的query_string部分
                if qs:
                    kw=dict()
                    for k,v in parse.parse_qs(qs,True).items():#parse.parse_qs(传入request参数的query部分，结果返回一个字典。
                        kw[k]=v[0]
        if kw==None:
            kw = dict(**request.match_info)
            print('***********%s'%request.match_info)
        else:
            print('***********%s'%request.match_info)
            if not self._has_var_kw_args and self._named_kw_args:
                copy = dict()
                for name in self._named_kw_args:
                    if name in kw:
                        copy[name] = kw[name]
                kw = copy
            for k,v in request.match_info.items():
                if k in kw:
                    logging.warning("Duplicate arg name in named arg and kw args:%s"%k)#重复的参数
                kw[k]=v

        if self._has_request_arg:
            kw["request"] = request
        if self._required_kw_args:
            for name in self._required_kw_args:
                if name not in kw:#若name不在KW中
                    return web.HTTPBadRequest("Missing arguments:%s"%name)
        logging.info("call with args:%s"%str(kw))
        try:
            r=yield from self._func(**kw)
            return r
        except APIError as e:
            return dict(error=e.error,data=e.data,message=e.message)
def add_static(app):#添加静态资源路径
     path=os.path.join(os.path.dirname(os.path.abspath(__file__)),"static")
     app.router.add_static("/static/",path)
     logging.info("add static %s => %s"%("/static/",path))
def add_route(app,fn):#注册函数，有效内容其实就是最后一句。可以参考廖雪峰aiohttp的示例。
    method = getattr(fn,"__method__",None)
    path = getattr(fn,"__route__",None)
    if path is None or method is None:
        raise ValueError("@get or @post not define in %s"%str(fn))
    if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
        fn=asyncio.coroutine(fn)
    logging.info("add route %s %s => %s(%s)"%(method,path,fn.__name__,",".join(inspect.signature(fn).parameters.keys())))
    app.router.add_route(method,path,RequestHandler(app,fn))#此处app.router.add_route与该函数add_route不是同一个东西 \
    #app=web.Application(),app.router是app中的一个类，add_route以及上文中出现的add_static均为这个类的方法，所以这两个函数只是对app.router的两个方法进行了封装。
    #app.router.add_route('GET', '/hello/{name}', hello)
    
def add_routes(app,module_name):#批量导入函数（存疑）
    n=module_name.rfind(".")#返回"."所在的位置n
    if n==(-1):
        mod=__import__(module_name,globals(),locals())#import handlers as mod ,handlers模块中的所有attr
    else:
        name=module_name[n+1:]
        mod = getattr(__import__(module_name[:n],globals(),locals(),[name]),name)#handlers模块内的某一个类的所有attr
        #__import__(module_name[:n],globals(),locals(),[name])这一句的意思等同于from XXX import XXX
        #getattr作用类似下面的获得函数fn
    for attr in dir(mod):
        if attr.startswith('_'):
            continue
        fn=getattr(mod,attr)#getattr获得的结果为<function index at 0x01D7BCD8>
        if callable(fn):
            method=getattr(fn,"__method__",None)
            path=getattr(fn,"__route__",None)
            if method and path:
                add_route(app,fn)
