import orm,asyncio
from models import User,Blog,Comment

@asyncio.coroutine
def test(loop):
	yield from orm.create_pool(loop=loop,user='root',password='19940828',db='awesome')
	u=User(name='Test',email='173544',passwd='123456',image='about:blank')
	#yield from u.save()
	User.findall()

loop=asyncio.get_event_loop()
loop.run_until_complete(test(loop))
loop.run_forever()
loop.close()