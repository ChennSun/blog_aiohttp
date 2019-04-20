#!/user/bin/env python3
# -*- coding:utf-8 -*-

__author__="sunchen"

'''
async orm
'''
import aiomysql,asyncio
import logging; logging.basicConfig(level=logging.INFO,format='%(asctime)s-%(levelname)s-%(message)s')

def log(sql,args=()):
	logging.info('SQL:%s'%sql)
	
@asyncio.coroutine
def create_pool(loop,**kw):#可变参数在函数调用时自动组装为一个tuple。而关键字参数允许你传入0个或任意个含参数名的参数，这些关键字参数在函数内部自动组装为一个dict
	logging.info('create datebase connection pool...')
	global __pool
	__pool=yield from aiomysql.create_pool(
	host=kw.get("host",'localhost'),#dict有一个get方法，如果dict中有对应的value值，则返回对应于key的value值，否则返回默认值，例如下面的host，如果dict里面没有'host',则返回后面的默认值，也就是'localhost'
	port=kw.get('port',3306),
	user=kw['user'],
	password=kw['password'],
	db=kw['db'],
	charset=kw.get('charset','utf8'),
	autocommit=kw.get("autocommit",True),
	maxsize=kw.get("maxsize",10),
	minsize=kw.get("minsize",1),
	loop=loop
	)
	
@asyncio.coroutine
def select(sql,args,size=None):
	log(sql,args)
	global __pool
	with (yield from __pool) as conn:#若使用await,可写成async with __pool.get()/__pool.acquire() as e 
		cur=yield from conn.cursor(aiomysql.DictCursor)
		yield from cur.execute(sql.replace("?",'%s'),args or())
		if size:
			rs=yield from cur.fetchmany(size)
		else:
			rs=yield from cur.fetchall()
		yield from cur.close()
		logging.info("row return:%s"%len(rs))
		return rs

@asyncio.coroutine
def execute(sql,args,autocommit=True):
	log(sql) #错误log(sql,args)
	global __pool
	with (yield from __pool) as conn:
		if not autocommit:
			yield from conn.begin()
		try:
			cur=yield from conn.cursor()
			yield from cur.execute(sql.replace("?","%s"),args)
			affected=cur.rowcount
			if not autocommit:
				yield from conn.commit()
		except BaseException as e:
			if not autocommit:
				yield from conn.rollback()
			raise
		return affected
def create_args_string(num):
	l=[]
	for n in range(num):
		l.append("?")
	return ', '.join(l)#用'，'连接l中的元素，将l转换为字符串。
"""
class User(Model):
	__table__="users"
	id=IntegerField(primary_key=True)
	name=StringField()
"""
class Field(object):
	def __init__(self,name,column_type,primary_key,default):
		self.name=name
		self.column_type=column_type
		self.primary_key=primary_key
		self.default=default
	def __str__(self):
		return "<%s,%s:%s>"%(self.__class__.__name__,self.column_type,self.name)

class StringField(Field):
	def __init__(self,name=None,primary_key=False,default=None,ddl='varchar(100)'):
		super().__init__(name,ddl,primary_key,default)
class BooleanField(Field):
	def __init__(self,name=None,default=False):
		super().__init__(name,'boolean',False,default)# 布尔类型不可以作为主键
class IntergerField(Field):
	def __init__(self,name=None,primary_key=False,default=0):
		super().__init__(name,"bigint",primary_key,default)
class FloatField(Field):
	def __init__(self,name=None,primary_key=False,default=0.0):
		super().__init__(name,"real",primary_key,default)
class TextField(Field):
	def __init__(self,name=None,default=None):
		super().__init__(name,"text",False,default)
		
class ModelMetaclass(type):
	# __new__:类里面的构造方法init()负责将类的实例化，而在init()调用之前，new()决定是否要使用该init()方法，如果new()没有返回cls（即当前类）的实例，那么当前类的init()方法是不会被调用 的。
	#         如果new()返回其他类（新式类或经典类均可）的实例，那么只会调用被返回的那个类的构造方法。
	# cls:代表要__init__的类（对象），此参数在实例化时由Python解释器自动提供(存疑)
	# name:类的名字(Model,User等)
	# bases:代表类继承的父类（dict）
	# attrs：类的方法集合
	def __new__(cls,name,bases,attrs):
		if name=="Model":
			return type.__new__(cls,name,bases,attrs)
		tableName=attrs.get('__table__',None) or name
		logging.info("found model:%s(table:%s)"%(name,tableName))
		mappings=dict()#获取所有属性名及对应类型，字典
		fields=[]#fields保存除主键之外的属性名，列表
		primaryKey=None
		#判断主键是否重复及主键是否存在
		for k,v in attrs.items():
			if isinstance(v,Field):
				logging.info('  found mapping:%s ==> %s'%(k,v))
				mappings[k]=v
				if v.primary_key:
					if primaryKey:
						raise StandardError('Duplicate primary key for field:%s'%k)
					primaryKey=k
				else:
					fields.append(k)
		if not primaryKey:
			raise StandardError('primary key not found')
		for k in mappings.keys():
			attrs.pop(k)#删除attrs（字典）中的 相关Field属性，只剩下方法
		escaped_fields=list(map(lambda f:'`%s`'%f,fields))#map(function,iterable),map()传入的第一个参数是函数对象本身。由于结果是一个Iterator，Iterator是惰性序列，因此通过list()函数让它把整个序列都计算出来并返回一个list。
		attrs['__mappings__']=mappings
		attrs['__tabale__']=tableName
		attrs['__primary_key__']=primaryKey
		attrs["__fields__"]=fields
		attrs['__select__']='select `%s`,%s from `%s`'%(primaryKey,','.join(escaped_fields),tableName)
		attrs['__insert__']='insert into `%s`(%s,`%s`)values(%s)'%(tableName,','.join(escaped_fields),primaryKey,create_args_string(len(escaped_fields)+1))
		attrs['__update__']='update `%s` set %s where `%s`=?'%(tableName,','.join(map(lambda f:'`%s`=?'%(mappings.get(f).name or f),fields)),primaryKey)
		attrs['__delete__']='delete from `%s` where `%s`=?'%(tableName,primaryKey)
		#attrs['__create_table__']='create table `%s` (`%s` )'
		return type.__new__(cls,name,bases,attrs)
	
class Model(dict,metaclass=ModelMetaclass):
	def __init__(self,**kw):
		super(Model,self).__init__(**kw)
	def __getattr__(self,key):
		try:
			return self[key]
		except KeyError:
			raise AttributeError(r"'Model' object has no attribute'%s'"%key)
	def __setattr__(self,key,value):#所有self.key=value赋值都会变成self.__setattr__(key,value),故点操作实质都变成了字典操作；
		self[key]=value
	def getValue(self,key):
		return getattr(self,key,None)  #若该属性存在返回属性key值，若该值不存在则返回None
	def getValueOrDefault(self,key):
		value=getattr(self,key,None)
		if value is None:
			field=self.__mappings__[key]
			if field.default is not None:
				#if callable(field.default)为真，采用field.default(),否则采用field.default
				value=field.default() if callable(field.default) else field.default#callable(object)；callable() 函数用于检查一个对象是否是可调用的。如果返回True，object仍然可能调用失败；但如果返回False，调用对象ojbect绝对不会成功。对于函数, 方法, lambda 函式, 类, 以及实现了 __call__ 方法的类实例, 它都返回 True。
				logging.debug("using default value for %s:%s"%(key,str(value)))
				setattr(self,key,value)
		return value
	@classmethod
	def create_database(self):
		pass
	@classmethod
	@asyncio.coroutine
	def findAll(cls,where=None,args=None,**kw):
		sql=[cls.__select__]
		if where:
			sql.append('where')
			sql.append(where)
		if args is None:
			args=[]
		orderBy=kw.get('orderBy',None)
		if orderBy:
			sql.append('order by')
			sql.append(orderBy)
		limit=kw.get('limit',None)
		if limit is not None:
			sql.append('limit')
			if isinstance(limit,int):
				sql.append('?')
				args.append(limit)
			elif isinstance(limit,tuple) and len(limit)==2:
				sql.append('?,?')
				args.extend(limit)#extend() 函数用于在列表末尾一次性追加另一个序列中的多个值（用新列表扩展原来的列表），limit为一个列表
			else:
				raise ValueError('Invalid limit value %s'%str(limit))
		rs = yield from select(' '.join(sql),args)
		return [cls(**r) for r in rs]
	@classmethod
	@asyncio.coroutine
	def findNumber(cls,selectField,where=None,args=None):
		sql=['select %s _num_ from `%s`'%(selectField,cls.__table__)]
		if where:
			sql.append('where')
			sql.append(where)
		rs=yield from select(" ".join(sql),args,1)
		if len(rs)==0:
			return None
		return rs[0]['_num_']
	@classmethod
	@asyncio.coroutine
	def find(cls,pk):
		rs=yield from select("%s where `%s` =?"%(cls.__select__,cls.__primary_key__),[pk],1)
		if len(rs)==0:
			return None
		return cls(**rs[0])
	@asyncio.coroutine
	def update(self):
		args=list(map(self.getValue,self.__fields__))
		args.append(self.getValue(self.__primary_key__))
		rows=yield from execute(self.__update__,args)
		if rows!=1:
			logging.warn("failed to update by primary key:affected rows:%s"%rows)
	@asyncio.coroutine
	def save(self):
		args = list(map(self.getValueOrDefault, self.__fields__))
		args.append(self.getValueOrDefault(self.__primary_key__))
		rows = yield from execute(self.__insert__, args)
		if rows != 1:
			logging.warn('failed to insert record: affected rows: %s' % rows)
	@asyncio.coroutine
	def remove(self):
		args=[self.getValue(self.__primary_key__)]
		rows=yield from execute(self.__delete__,args)
		if rows!=1:
			logging.warn('failed to remove record: affected rows: %s' % rows)