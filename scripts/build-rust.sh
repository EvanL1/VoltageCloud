#!/bin/bash
# Build Rust Lambda for IoT PoC

set -e

echo "🦀 Building Rust Lambda processor..."

# Check if cargo-lambda is installed
if ! command -v cargo-lambda > /dev/null; then
    echo "📦 Installing cargo-lambda..."
    cargo install cargo-lambda
fi

# Navigate to rust-lambda directory
cd rust-lambda

# Build for Lambda ARM64 runtime
echo "🔨 Building Rust Lambda for ARM64..."
cargo lambda build --release --arm64

# Create deployment package
echo "📦 Creating deployment package..."
mkdir -p ../lambda-rust
cp target/lambda/iot-poc-processor/bootstrap ../lambda-rust/

echo "✅ Rust Lambda build completed!"
echo "📁 Binary location: lambda-rust/bootstrap"
echo ""
echo "🔧 To deploy with Rust Lambda:"
echo "1. Update iot_poc_stack.py to use lambda-rust directory"
echo "2. Change runtime to PROVIDED_AL2 and architecture to ARM_64"
echo "3. Set handler to 'bootstrap'"
echo "4. Run: cdk deploy"

cd .. 