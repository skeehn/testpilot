from setuptools import setup, find_packages

setup(
    name='testpilot',
    version='0.1.0',
    description='AI-powered test generation, execution, and triage CLI',
    author='Your Name',
    packages=find_packages(),
    install_requires=[
        'click',
        'openai',
        'PyGithub',
        'pytest',
    ],
    entry_points={
        'console_scripts': [
            'testpilot = testpilot.cli:cli',
        ],
    },
    python_requires='>=3.7',
) 