from setuptools import setup

setup(
    name='flaws',
    version='0.0.1',
    author='Alexander Schepanovski',
    author_email='suor.web@gmail.com',

    description='Finds flaws in your python code',
    long_description=open('README.rst').read(),
    url='http://github.com/Suor/flaws',
    license='BSD',

    py_modules=['astpp'],
    packages=['flaws'],

    install_requires=[
        'funcy>=1.1',
    ],
    entry_points = {
        'console_scripts': [
            'flaws = flaws:main',
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
