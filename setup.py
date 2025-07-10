from setuptools import setup, find_packages
import os

# Read version from package
def get_version():
    init_path = os.path.join(os.path.dirname(__file__), 'testpilot', '__init__.py')
    with open(init_path, 'r') as f:
        for line in f:
            if line.startswith('__version__'):
                return line.split('=')[1].strip().strip('"\'')
    return '0.1.0'

# Read README for long description
with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='testpilot',
    version=get_version(),
    description='AI-powered test generation, execution, and triage CLI for Python projects',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='TestPilot Authors',
    url='https://github.com/yourusername/testpilot',
    packages=find_packages(),
    install_requires=[
        'click',
        'openai',
        'PyGithub',
        'pytest',
        'python-dotenv',
    ],
    entry_points={
        'console_scripts': [
            'testpilot = testpilot.cli:cli',
        ],
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Software Development :: Testing',
        'Topic :: Software Development :: Quality Assurance',
    ],
    python_requires='>=3.7',
    keywords='testing, ai, llm, pytest, automation, triage',
) 