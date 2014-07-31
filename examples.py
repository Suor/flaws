def password_filter(data):
    '''replace passwords with ****'''
    key, value = data
    if 'password' in key:
        value = '*****'
    return (key, value)
filtered_data = walk(password_filter, self.data)
# dict comprehension:
filtered_data = {key: '****' if key == 'password' else value
                 for key, value in self.data.items()}
# just assignment:
filtered_data = self.data.copy()
filtered_data['password'] = '****'


partial(operator.eq, task)
# operator partial application
task.__eq__


class A(object):
    def __contains__(self, task):
            return any(partial(operator.eq, task), self)
# Completely useless, reimplements default behaviour


tasks = ifilter(partial(operator.ne, self.task(task)), self)
# use iwithout:
tasks = iwithout(self, self.task(task))

select(query, self.iterate(raw=True))
# use ifilter instead of select:
ifilter(query, self.iterate(raw=True))


if key in ('SECRET_KEY',):
        return '******'
# just ==:
if key == 'SECRET_KEY':
        return '******'


walk(reversed, settings.KONOHA_TEMPLATES)[obj.template]
# flip:
flip(settings.KONOHA_TEMPLATES)[obj.template]


try:
    return some_dict[obj.template]
except KeyError:
    return obj.template
# dict.get:
return some_dict.get(obj.template, obj.template)

