#!/usr/bin/env python
#
#===- add_new_check.py - clang-tidy check generator ----------*- python -*--===#
#
#                     The LLVM Compiler Infrastructure
#
# This file is distributed under the University of Illinois Open Source
# License. See LICENSE.TXT for details.
#
#===------------------------------------------------------------------------===#

import os
import re
import sys


# Adapts the module's CMakelist file. Returns 'True' if it could add a new entry
# and 'False' if the entry already existed.
def adapt_cmake(module_path, check_name_camel):
  filename = os.path.join(module_path, 'CMakeLists.txt')
  with open(filename, 'r') as f:
    lines = f.read().split('\n')
  # .split with separator returns one more element. Ignore it.
  lines = lines[:-1]

  cpp_file = check_name_camel + '.cpp'

  # Figure out whether this check already exists.
  for line in lines:
    if line.strip() == cpp_file:
      return False

  with open(filename, 'w') as f:
    cpp_found = False
    file_added = False
    for line in lines:
      if not file_added and (line.endswith('.cpp') or cpp_found):
        cpp_found = True
        if line.strip() > cpp_file:
          f.write('  ' + cpp_file + '\n')
          file_added = True
      f.write(line + '\n')

  return True


# Adds a header for the new check.
def write_header(module_path, module, check_name, check_name_camel):
  filename = os.path.join(module_path, check_name_camel) + '.h'
  with open(filename, 'w') as f:
    header_guard = ('LLVM_CLANG_TOOLS_EXTRA_CLANG_TIDY_' + module.upper() +
                    '_' + check_name.upper().replace('-', '_') + '_H')
    f.write('//===--- ')
    f.write(os.path.basename(filename))
    f.write(' - clang-tidy')
    f.write('-' * max(0, 43 - len(os.path.basename(filename))))
    f.write('*- C++ -*-===//')
    f.write("""
//
//                     The LLVM Compiler Infrastructure
//
// This file is distributed under the University of Illinois Open Source
// License. See LICENSE.TXT for details.
//
//===----------------------------------------------------------------------===//

#ifndef %(header_guard)s
#define %(header_guard)s

#include "../ClangTidy.h"

namespace clang {
namespace tidy {

class %(check_name)s : public ClangTidyCheck {
public:
  %(check_name)s(StringRef Name, ClangTidyContext *Context)
      : ClangTidyCheck(Name, Context) {}
  void registerMatchers(ast_matchers::MatchFinder *Finder) override;
  void check(const ast_matchers::MatchFinder::MatchResult &Result) override;
};

} // namespace tidy
} // namespace clang

#endif // %(header_guard)s

""" % {'header_guard': header_guard,
       'check_name': check_name_camel})


# Adds the implementation of the new check.
def write_implementation(module_path, check_name_camel):
  filename = os.path.join(module_path, check_name_camel) + '.cpp'
  with open(filename, 'w') as f:
    f.write('//===--- ')
    f.write(os.path.basename(filename))
    f.write(' - clang-tidy')
    f.write('-' * max(0, 52 - len(os.path.basename(filename))))
    f.write('-===//')
    f.write("""
//
//                     The LLVM Compiler Infrastructure
//
// This file is distributed under the University of Illinois Open Source
// License. See LICENSE.TXT for details.
//
//===----------------------------------------------------------------------===//

#include "%(check_name)s.h"
#include "clang/AST/ASTContext.h"
#include "clang/ASTMatchers/ASTMatchFinder.h"

using namespace clang::ast_matchers;

namespace clang {
namespace tidy {

void %(check_name)s::registerMatchers(MatchFinder *Finder) {
  // FIXME: Add matchers.
  Finder->addMatcher(functionDecl().bind("x"), this);
}

void %(check_name)s::check(const MatchFinder::MatchResult &Result) {
  // FIXME: Add callback implementation.
  const auto *MatchedDecl = Result.Nodes.getNodeAs<FunctionDecl>("x");
  if (MatchedDecl->getName().startswith("awesome_"))
    return;
  diag(MatchedDecl->getLocation(), "function '%%0' is insufficiently awesome")
      << MatchedDecl->getName()
      << FixItHint::CreateInsertion(MatchedDecl->getLocation(), "awesome_");
}

} // namespace tidy
} // namespace clang

""" % {'check_name': check_name_camel})


# Modifies the module to include the new check.
def adapt_module(module_path, module, check_name, check_name_camel):
  filename = os.path.join(module_path, module.capitalize() + 'TidyModule.cpp')
  with open(filename, 'r') as f:
    lines = f.read().split('\n')
  # .split with separator returns one more element. Ignore it.
  lines = lines[:-1]

  with open(filename, 'w') as f:
    header_added = False
    header_found = False
    check_added = False
    check_decl = ('    CheckFactories.registerCheck<' + check_name_camel +
                  '>(\n        "' + module + '-' + check_name + '");\n')

    for line in lines:
      if not header_added:
        match = re.search('#include "(.*)"', line)
        if match:
          header_found = True
          if match.group(1) > check_name_camel:
            header_added = True
            f.write('#include "' + check_name_camel + '.h"\n')
        elif header_found:
          header_added = True
          f.write('#include "' + check_name_camel + '.h"\n')

      if not check_added:
        if line.strip() == '}':
          check_added = True
          f.write(check_decl)
        else:
          match = re.search('registerCheck<(.*)>', line)
          if match and match.group(1) > check_name_camel:
            check_added = True
            f.write(check_decl)
      f.write(line + '\n')


# Adds a test for the check.
def write_test(module_path, module, check_name):
  check_name_dashes = module + '-' + check_name
  filename = os.path.join(module_path, '../../test/clang-tidy',
                          check_name_dashes + '.cpp')
  with open(filename, 'w') as f:
    f.write(
"""// RUN: $(dirname %%s)/check_clang_tidy.sh %%s %(check_name_dashes)s %%t
// REQUIRES: shell

// FIXME: Add something that triggers the check here.
void f();
// CHECK-MESSAGES: :[[@LINE-1]]:6: warning: function 'f' is insufficiently awesome [%(check_name_dashes)s]

// FIXME: Verify the applied fix.
//   * Make the CHECK patterns specific enough and try to make verified lines
//     unique to avoid incorrect matches.
//   * Use {{}} for regular expressions.
// CHECK-FIXES: {{^}}void awesome_f();{{$}}

// FIXME: Add something that doesn't trigger the check here.
void awesome_f2();
""" % {"check_name_dashes" : check_name_dashes})

def main():
  if len(sys.argv) != 3:
    print 'Usage: add_new_check.py <module> <check>, e.g.\n'
    print 'add_new_check.py misc awesome-functions\n'
    return

  module = sys.argv[1]
  check_name = sys.argv[2]
  check_name_camel = ''.join(map(lambda elem: elem.capitalize(),
                                 check_name.split('-'))) + 'Check'
  clang_tidy_path = os.path.dirname(sys.argv[0])
  module_path = os.path.join(clang_tidy_path, module)

  if not adapt_cmake(module_path, check_name_camel):
    return
  write_header(module_path, module, check_name, check_name_camel)
  write_implementation(module_path, check_name_camel)
  adapt_module(module_path, module, check_name, check_name_camel)
  write_test(module_path, module, check_name)


if __name__ == '__main__':
  main()
