#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

'''
JSON API definition.
'''

import json, logging, inspect, functools

class Page(object):
    def __init__(self,item_count,page_index=1,page_size=10):#文章总数，第几页，每页多少篇文章。
        self.item_count=item_count#文章总数或文章编号，意思差不多
        self.page_size=page_size#每页文章数量
        self.page_count=item_count//page_size+(1 if item_count%page_size>0 else 0)#总共有多少页
        if (item_count==0) or (page_index>self.page_count):#如果文章总数为零，或文章数量不足一页。
            self.offset=0
            self.limit=0
            self.page_index=1
        else:
            self.page_index=page_index
            self.offset=self.page_size * (page_index - 1)#每页文章从第几个开始。第一页0-10，第二页10-20
            self.limit=self.page_size#orm中数据库函数findAll，返回固定数量的数据。
        self.has_next=self.page_index<self.page_count#是否有下一页
        self.has_previous=self.page_index>1#是否有上一页
    def __str__(self):
        return "item_count:%s,page_count:%s,page_index:%s,page_size:%s,offset:%s,limit:%s"%(self.item_count,self.page_count,self.page_index,self.page_size,self.offset,self.limit)

    __repr__=__str__

class APIError(Exception):
    '''
    the base APIError which contains error(required), data(optional) and message(optional).
    '''
    def __init__(self, error, data='', message=''):
        super(APIError, self).__init__(message)
        self.error = error
        self.data = data
        self.message = message

class APIValueError(APIError):
    '''
    Indicate the input value has error or invalid. The data specifies the error field of input form.
    '''
    def __init__(self, field, message=''):
        super(APIValueError, self).__init__('value:invalid', field, message)

class APIResourceNotFoundError(APIError):
    '''
    Indicate the resource was not found. The data specifies the resource name.
    '''
    def __init__(self, field, message=''):
        super(APIResourceNotFoundError, self).__init__('value:notfound', field, message)

class APIPermissionError(APIError):
    '''
    Indicate the api has no permission.
    '''
    def __init__(self, message=''):
        super(APIPermissionError, self).__init__('permission:forbidden', 'permission', message)
