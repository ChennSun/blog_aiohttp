#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import config_default
class Dict(dict):
	def __init__(self,names=(),values=(),**kw):
		super(Dict,self).__init__(**kw)
		m1={}
		for k,v in zip(names,values):
			m1[k]=v
	def __getattr__(self,key):
		try:
			return self[key]
		except:
			raise AttributeError(r"'Dict'object has no attribute '%s'"%key)
	def __setattr__(self,key,value):
		self[key]=value
		print 

def merge(defaults,override):
	r={}
	for k,v in defaults.items():
		if k in override:
			if isinstance(v,dict):
				 r[k]=merge(defaults[k],override[k])
			else:
				r[k]=override[k]
		else:
			r[k]=v
	return r
def todict(d):
	D=Dict()
	for k,v in d.items():
		D[k]=todict(v) if isinstance(v,dict) else v
	return D

configs=config_default.configs
try:
	import config_override
	configs=merge(configs,config_override.configs)#此时m为一个字典
except:
	pass

configs=todict(configs)
if __name__ =="__main__":
	print(configs['debug'])