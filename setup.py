from setuptools import setup

setup(
    name='iron',
    version='0.0.1',
    author='Alexander Schepanovski',
    author_email='suor.web@gmail.com',

    description='Iron out your python code.',
    long_description=open('README.rst').read(),
    url='http://github.com/Suor/iron',
    license='BSD',

    py_modules=['iron', 'astpp'],
    install_requires=[
        'funcy>=1.1',
    ],
    entry_points = {
        'console_scripts': [
            'iron = iron:main',
        ],
    },

    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Environment :: Console',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',

        'Intended Audience :: Developers',
        'Topic :: Software Development :: Quality Assurance',
        'Topic :: Utilities',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
