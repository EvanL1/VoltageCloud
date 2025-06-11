"""
Simple test to demonstrate conda environment functionality
"""

import pytest
import sys
import os
from pathlib import Path


class TestCondaEnvironment:
    """Test conda environment functionality"""
    
    @pytest.mark.unit
    def test_python_version(self):
        """Test Python version in conda environment"""
        assert sys.version_info.major == 3
        assert sys.version_info.minor == 9
        print(f"✅ Python version: {sys.version}")
    
    @pytest.mark.unit
    def test_environment_packages(self):
        """Test that required packages are available"""
        try:
            import boto3
            print(f"✅ boto3 version: {boto3.__version__}")
        except ImportError:
            pytest.fail("boto3 not available")
        
        try:
            import pytest as pt
            print(f"✅ pytest version: {pt.__version__}")
        except ImportError:
            pytest.fail("pytest not available")
    
    @pytest.mark.unit
    def test_working_directory(self):
        """Test working directory is correct"""
        cwd = Path.cwd()
        print(f"✅ Current working directory: {cwd}")
        assert cwd.name == "cloud"
    
    @pytest.mark.unit
    def test_environment_variables(self):
        """Test environment variables"""
        # Check basic environment
        print(f"✅ PATH: {os.environ.get('PATH', 'Not set')[:100]}...")
        
        # Check conda environment if available
        conda_env = os.environ.get('CONDA_DEFAULT_ENV')
        if conda_env:
            print(f"✅ Conda environment: {conda_env}")
        
        conda_prefix = os.environ.get('CONDA_PREFIX')
        if conda_prefix:
            print(f"✅ Conda prefix: {conda_prefix}")
    
    @pytest.mark.unit
    def test_project_structure(self):
        """Test that project structure is accessible"""
        project_root = Path.cwd()
        
        # Check for key directories
        iot_poc_dir = project_root / "iot_poc"
        assert iot_poc_dir.exists(), "iot_poc directory should exist"
        print(f"✅ iot_poc directory found: {iot_poc_dir}")
        
        lambda_dir = project_root / "lambda"
        assert lambda_dir.exists(), "lambda directory should exist"
        print(f"✅ lambda directory found: {lambda_dir}")
        
        tests_dir = project_root / "tests"
        assert tests_dir.exists(), "tests directory should exist"
        print(f"✅ tests directory found: {tests_dir}")
    
    @pytest.mark.unit
    def test_aws_sdk_basic(self):
        """Test basic AWS SDK functionality (without credentials)"""
        import boto3
        
        # This should work without credentials for basic functionality
        session = boto3.Session()
        print(f"✅ boto3 session created: {session}")
        
        # Test getting available services
        available_services = session.get_available_services()
        assert 'sqs' in available_services
        assert 's3' in available_services
        assert 'dynamodb' in available_services
        print(f"✅ AWS services available: {len(available_services)} services")


@pytest.mark.unit
def test_simple_conda_functionality():
    """Simple test to verify conda environment is working"""
    print("\n🐍 Testing Conda Environment Functionality")
    print("=" * 50)
    
    # Test Python executable
    python_exe = sys.executable
    print(f"Python executable: {python_exe}")
    
    # Test if we're in a conda environment
    if "conda" in python_exe or "Conda" in python_exe:
        print("✅ Running in conda environment")
    else:
        print("⚠️  May not be running in conda environment")
    
    # Test imports
    imports_to_test = [
        'boto3', 'pytest', 'json', 'os', 'sys', 'pathlib'
    ]
    
    successful_imports = []
    for module in imports_to_test:
        try:
            __import__(module)
            successful_imports.append(module)
            print(f"✅ {module} imported successfully")
        except ImportError as e:
            print(f"❌ {module} import failed: {e}")
    
    assert len(successful_imports) >= 4, "At least 4 basic modules should import successfully"
    print(f"\n🎉 Test completed! {len(successful_imports)}/{len(imports_to_test)} modules imported successfully")


if __name__ == "__main__":
    # For direct execution
    test_simple_conda_functionality() 