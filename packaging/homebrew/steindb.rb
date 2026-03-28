class Exodusdb < Formula
  include Language::Python::Virtualenv

  desc "AI-powered Oracle-to-PostgreSQL migration tool"
  homepage "https://steindb.com"
  url "https://files.pythonhosted.org/packages/source/e/steindb/steindb-0.1.0.tar.gz"
  sha256 "PLACEHOLDER"
  license "Apache-2.0"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "SteinDB CLI v", shell_output("#{bin}/stein --version")
  end
end
