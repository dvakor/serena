"""
Basic integration tests for the BSL (1C:Enterprise) language server functionality.

These tests validate the functionality of the language server APIs
like request_document_symbols using the BSL test repository.
"""

import pytest

from solidlsp import SolidLanguageServer
from solidlsp.ls_config import Language


@pytest.mark.bsl
class TestBslLanguageServerBasics:
    """Test basic functionality of the BSL language server."""

    @pytest.mark.parametrize("language_server", [Language.BSL], indirect=True)
    def test_bsl_language_server_initialization(self, language_server: SolidLanguageServer) -> None:
        """Test that BSL language server can be initialized successfully."""
        assert language_server is not None
        assert language_server.language == Language.BSL

    @pytest.mark.parametrize("language_server", [Language.BSL], indirect=True)
    def test_bsl_request_document_symbols_main(self, language_server: SolidLanguageServer) -> None:
        """Test request_document_symbols for Main.bsl file."""
        all_symbols, _root_symbols = language_server.request_document_symbols("Main.bsl").get_all_symbols_and_roots()

        # Extract symbol names
        symbol_names = [symbol["name"] for symbol in all_symbols]

        # Should detect functions and procedures from Main.bsl
        # Note: BSL LS may report names in different formats depending on version
        assert len(all_symbols) > 0, "Should find symbols in Main.bsl"

        # Check for expected functions/procedures (in Russian or transliterated)
        expected_symbols = [
            "ПриветствоватьПользователя",
            "ОбработатьЭлементы",
            "ИнициализироватьПеременные",
            "Главная",
        ]

        found_expected = sum(1 for expected in expected_symbols if any(expected in name for name in symbol_names))
        assert found_expected >= 2, f"Should find at least 2 expected functions. Found symbols: {symbol_names}"

    @pytest.mark.parametrize("language_server", [Language.BSL], indirect=True)
    def test_bsl_request_document_symbols_utils(self, language_server: SolidLanguageServer) -> None:
        """Test request_document_symbols for Utils.bsl file."""
        all_symbols, _root_symbols = language_server.request_document_symbols("Utils.bsl").get_all_symbols_and_roots()

        # Extract symbol names
        symbol_names = [symbol["name"] for symbol in all_symbols]

        # Should detect functions from Utils.bsl
        expected_functions = [
            "ВВерхнийРегистр",
            "ВНижнийРегистр",
            "УбратьПробелы",
            "ЭтоЧисло",
            "ПроверитьEmail",
            "ЗаписатьВЛог",
            "СоздатьРезервнуюКопию",
            "СодержитЭлемент",
        ]

        found_count = sum(1 for func in expected_functions if any(func in name for name in symbol_names))
        assert found_count >= 4, f"Should find at least 4 utility functions. Found symbols: {symbol_names}"

    @pytest.mark.parametrize("language_server", [Language.BSL], indirect=True)
    def test_bsl_request_document_symbols_model(self, language_server: SolidLanguageServer) -> None:
        """Test request_document_symbols for Model.bsl file."""
        all_symbols, _root_symbols = language_server.request_document_symbols("Model.bsl").get_all_symbols_and_roots()

        # Extract symbol names
        symbol_names = [symbol["name"] for symbol in all_symbols]

        # Should detect model-related functions
        expected_functions = [
            "СоздатьПользователя",
            "ВалидироватьПользователя",
            "СоздатьЗаказ",
            "ДобавитьТоварВЗаказ",
            "СоздатьТовар",
        ]

        found_count = sum(1 for func in expected_functions if any(func in name for name in symbol_names))
        assert found_count >= 3, f"Should find at least 3 model functions. Found symbols: {symbol_names}"

    @pytest.mark.parametrize("language_server", [Language.BSL], indirect=True)
    def test_bsl_full_symbol_tree(self, language_server: SolidLanguageServer) -> None:
        """Test request_full_symbol_tree for the entire BSL project."""
        symbols = language_server.request_full_symbol_tree()

        # Should have symbols from all files
        assert len(symbols) > 0, "Should find symbols in the project"

        # Flatten all symbol names for checking
        all_names = []

        def collect_names(symbol_list):
            for sym in symbol_list:
                all_names.append(sym.get("name", ""))
                if "children" in sym:
                    collect_names(sym["children"])

        collect_names(symbols)

        # Should have multiple symbols from different files
        assert len(all_names) >= 5, f"Should find at least 5 symbols across all files. Found: {len(all_names)}"

    @pytest.mark.parametrize("language_server", [Language.BSL], indirect=True)
    def test_bsl_symbol_kinds(self, language_server: SolidLanguageServer) -> None:
        """Test that BSL symbols have correct LSP symbol kinds."""
        all_symbols, _root_symbols = language_server.request_document_symbols("Main.bsl").get_all_symbols_and_roots()

        # LSP Symbol Kinds:
        # 12 = Function
        # 6 = Method
        # 13 = Variable

        function_kinds = {6, 12}  # Method or Function
        functions = [sym for sym in all_symbols if sym.get("kind") in function_kinds]

        assert len(functions) >= 2, f"Should find at least 2 functions/methods. Found: {len(functions)}"
