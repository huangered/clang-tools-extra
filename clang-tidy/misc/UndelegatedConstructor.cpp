//===--- UndelegatedConstructor.cpp - clang-tidy --------------------------===//
//
//                     The LLVM Compiler Infrastructure
//
// This file is distributed under the University of Illinois Open Source
// License. See LICENSE.TXT for details.
//
//===----------------------------------------------------------------------===//

#include "UndelegatedConstructor.h"
#include "clang/AST/ASTContext.h"
#include "clang/Lex/Lexer.h"

using namespace clang::ast_matchers;

namespace clang {

namespace ast_matchers {
AST_MATCHER_P(Stmt, ignoringTemporaryExpr, internal::Matcher<Stmt>,
              InnerMatcher) {
  const Stmt *E = &Node;
  for (;;) {
    // Temporaries with non-trivial dtors.
    if (const auto *EWC = dyn_cast<ExprWithCleanups>(E))
      E = EWC->getSubExpr();
    // Temporaries with zero or more than two ctor arguments.
    else if (const auto *BTE = dyn_cast<CXXBindTemporaryExpr>(E))
      E = BTE->getSubExpr();
    // Temporaries with exactly one ctor argument.
    else if (const auto *FCE = dyn_cast<CXXFunctionalCastExpr>(E))
      E = FCE->getSubExpr();
    else
      break;
  }

  return InnerMatcher.matches(*E, Finder, Builder);
}

// Finds a node if it's a base of an already bound node.
AST_MATCHER_P(CXXRecordDecl, baseOfBoundNode, std::string, ID) {
  return Builder->removeBindings([&](const internal::BoundNodesMap &Nodes) {
    const auto *Derived = Nodes.getNodeAs<CXXRecordDecl>(ID);
    return Derived != &Node && !Derived->isDerivedFrom(&Node);
  });
}
} // namespace ast_matchers

namespace tidy {
namespace misc {

void UndelegatedConstructorCheck::registerMatchers(MatchFinder *Finder) {
  // We look for calls to constructors of the same type in constructors. To do
  // this we have to look through a variety of nodes that occur in the path,
  // depending on the type's destructor and the number of arguments on the
  // constructor call, this is handled by ignoringTemporaryExpr. Ignore template
  // instantiations to reduce the number of duplicated warnings.
  Finder->addMatcher(
      compoundStmt(
          hasParent(constructorDecl(ofClass(recordDecl().bind("parent")))),
          forEach(ignoringTemporaryExpr(
              constructExpr(hasDeclaration(constructorDecl(ofClass(
                                recordDecl(baseOfBoundNode("parent"))))))
                  .bind("construct"))),
          unless(isInTemplateInstantiation())),
      this);
}

void UndelegatedConstructorCheck::check(const MatchFinder::MatchResult &Result) {
  const auto *E = Result.Nodes.getStmtAs<CXXConstructExpr>("construct");
  diag(E->getLocStart(), "did you intend to call a delegated constructor? "
                         "A temporary object is created here instead");
}

} // namespace misc
} // namespace tidy
} // namespace clang
