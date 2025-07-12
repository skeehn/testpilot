import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from testpilot.core import (
    generate_tests_llm,
    run_pytest_tests,
    create_github_issue,
    CodebaseAnalyzer,
    TestValidator,
)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for TestPilot CLI."""
    parser = argparse.ArgumentParser(
        description="🚀 TestPilot 2.0 - AI-Powered Test Generation Revolution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic test generation
  testpilot generate my_module.py

  # Context-aware generation with validation (recommended)
  testpilot generate my_module.py --use-context --validate

  # Generate and run tests
  testpilot generate my_module.py --run

  # Generate tests with specific provider
  testpilot generate my_module.py --provider anthropic --model claude-3-sonnet

For more information, visit: https://github.com/your-org/testpilot
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Generate command
    generate_parser = subparsers.add_parser(
        "generate", 
        help="Generate tests for Python files",
        description="Generate comprehensive unit tests using AI with advanced context awareness"
    )
    
    generate_parser.add_argument(
        "source_file", 
        help="Python source file to generate tests for"
    )
    
    # AI Provider options
    generate_parser.add_argument(
        "--provider",
        default="openai",
        choices=["openai", "anthropic", "azure-openai", "mistral", "huggingface"],
        help="AI provider to use (default: openai)"
    )
    generate_parser.add_argument("--model", help="Specific model to use")
    generate_parser.add_argument("--api-key", help="API key for the provider")
    generate_parser.add_argument("--temperature", type=float, help="Temperature for generation (0.0-1.0)")
    generate_parser.add_argument("--max-tokens", type=int, help="Maximum tokens to generate")

    # Context and Quality options  
    generate_parser.add_argument(
        "--use-context", 
        action="store_true",
        help="🧠 Enable context-aware generation (analyzes entire codebase)"
    )
    generate_parser.add_argument(
        "--validate", 
        action="store_true",
        help="✅ Enable quality validation and auto-retry"
    )
    generate_parser.add_argument(
        "--quality-threshold",
        type=float,
        default=0.8,
        help="Quality threshold for test acceptance (0.0-1.0, default: 0.8)"
    )

    # Output options
    generate_parser.add_argument(
        "--output", "-o", 
        help="Output file path (default: test_{source_filename}.py)"
    )
    generate_parser.add_argument(
        "--overwrite", 
        action="store_true",
        help="Overwrite existing test file"
    )
    generate_parser.add_argument(
        "--append", 
        action="store_true",
        help="Append to existing test file"
    )
    generate_parser.add_argument(
        "--quiet", "-q", 
        action="store_true",
        help="Suppress progress output"
    )

    # Execution options
    generate_parser.add_argument(
        "--run", 
        action="store_true",
        help="Run generated tests immediately"
    )

    # Advanced options
    generate_parser.add_argument("--prompt-file", help="Custom prompt template file")
    generate_parser.add_argument("--prompt-name", help="Named prompt template to use")
    generate_parser.add_argument(
        "--show-analysis",
        action="store_true",
        help="Show detailed codebase analysis results"
    )
    generate_parser.add_argument(
        "--show-validation",
        action="store_true", 
        help="Show detailed validation results"
    )

    # Run command
    run_parser = subparsers.add_parser("run", help="Run existing tests")
    run_parser.add_argument("test_file", help="Test file to run")
    run_parser.add_argument("--create-issues", action="store_true", help="Create GitHub issues for failures")
    run_parser.add_argument("--github-token", help="GitHub token for issue creation")
    run_parser.add_argument("--repo", help="GitHub repository (owner/repo)")

    return parser


def handle_generate_command(args):
    """Handle the generate command with enhanced features."""
    if not args.quiet:
        print("🚀 TestPilot 2.0 - Generating tests...")
        if args.use_context:
            print("🧠 Context analysis enabled")
        if args.validate:
            print("✅ Quality validation enabled")
    
    # Prepare generation arguments
    gen_kwargs = {
        "use_context_analysis": args.use_context,
        "validation_enabled": args.validate,
    }
    
    if args.temperature is not None:
        gen_kwargs["temperature"] = args.temperature
    if args.max_tokens is not None:
        gen_kwargs["max_tokens"] = args.max_tokens
    if args.prompt_file:
        gen_kwargs["prompt_file"] = args.prompt_file
    if args.prompt_name:
        gen_kwargs["prompt_name"] = args.prompt_name

    # Show context analysis if requested
    if args.show_analysis and args.use_context:
        print("\n🔍 Analyzing codebase...")
        analyzer = CodebaseAnalyzer(str(Path(args.source_file).parent))
        context = analyzer.get_project_context(args.source_file)
        
        target_analysis = context['target_analysis']
        print(f"📊 Found {len(target_analysis['functions'])} functions")
        print(f"🏗️ Found {len(target_analysis['classes'])} classes")
        print(f"📦 Found {len(target_analysis['imports'])} imports")
        
        testing_patterns = context['testing_patterns']
        if testing_patterns['common_imports']:
            print(f"🧪 Testing frameworks: {', '.join(testing_patterns['common_imports'])}")

    # Generate tests
    try:
        if not args.quiet:
            print("\n⚡ Generating tests...")
        
        test_code = generate_tests_llm(
            args.source_file,
            args.provider,
            model_name=args.model,
            api_key=args.api_key,
            **gen_kwargs
        )
        
        # Determine output file
        if args.output:
            output_file = args.output
        else:
            source_path = Path(args.source_file)
            output_file = f"test_{source_path.name}"
        
        # Check if file exists
        if os.path.exists(output_file) and not (args.overwrite or args.append):
            print(f"❌ Error: {output_file} already exists. Use --overwrite or --append")
            return 1
        
        # Write the test file
        mode = 'a' if args.append else 'w'
        with open(output_file, mode, encoding='utf-8') as f:
            if args.append:
                f.write("\n\n")
            f.write(test_code)
        
        if not args.quiet:
            action = "Appended to" if args.append else "Generated"
            print(f"✅ {action} {output_file}")
        
        # Show validation results if requested
        if args.show_validation and args.validate:
            print("\n📊 Validation Results:")
            validator = TestValidator()
            results = validator.validate_comprehensive(test_code, args.source_file)
            print(f"  Syntax valid: {'✅' if results['syntax_valid'] else '❌'}")
            print(f"  Tests execute: {'✅' if results['execution_results']['success'] else '❌'}")
            print(f"  Coverage score: {results['coverage_analysis']['coverage_score']:.1%}")
            print(f"  Quality score: {results['overall_quality_score']:.1%}")
        
        # Run tests if requested
        if args.run:
            if not args.quiet:
                print(f"\n🔧 Running tests in {output_file}...")
            
            output, failed, _ = run_pytest_tests(output_file, return_trace=True)
            
            if not args.quiet:
                print(output)
                if failed:
                    print("❌ Tests failed")
                else:
                    print("✅ All tests passed")
            
            return 1 if failed else 0
        
        return 0
        
    except Exception as e:
        print(f"❌ Error generating tests: {e}")
        return 1


def handle_run_command(args):
    """Handle the run command."""
    print(f"🔧 Running tests in {args.test_file}...")
    
    output, failed, trace = run_pytest_tests(args.test_file, return_trace=True)
    print(output)
    
    if failed:
        print("❌ Tests failed")
        
        if args.create_issues and args.repo:
            print("📝 Creating GitHub issue...")
            try:
                url = create_github_issue(
                    args.repo,
                    f"Test failure in {args.test_file}",
                    trace,
                    args.github_token or os.getenv("GITHUB_TOKEN")
                )
                print(f"✅ Issue created: {url}")
            except Exception as e:
                print(f"❌ Failed to create issue: {e}")
    else:
        print("✅ All tests passed")
    
    return 1 if failed else 0


def main():
    """Main CLI entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == "generate":
        return handle_generate_command(args)
    elif args.command == "run":
        return handle_run_command(args)
    else:
        print(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
