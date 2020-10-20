use peg;

pub mod ast {
    #[derive(Debug, PartialEq, Eq)]
    pub enum Arg<'a> {
        Var(&'a str),
        Word(&'a str),
    }

    pub type List<'a> = Vec<Arg<'a>>;

    #[derive(Debug, PartialEq, Eq)]
    pub enum Stmt<'a> {
        Assignment(Arg<'a>, List<'a>),
        Command(Arg<'a>, List<'a>),
    }
}

// mod parser
peg::parser! {
    grammar parser() for str {

        // ## Whitespace
        rule _() = quiet!{ [' ' | '\t'] }

        // ## Words
        //
        // The following characters have special meanings:
        rule chr() = !['#' | '$' | '|' | '&' | ';' | '(' | ')' | '<' | '>' | ' ' | '\t' | '\n'] [_]
        //
        // Special characters terminate words.
        pub rule word_unquoted() -> ast::Arg<'input> = w:$(chr()+) { ast::Arg::Word(w) }
        //
        // The single quote prevents special treatment of any character other than itself.
        pub rule word_quoted() -> ast::Arg<'input> = "'" s:$((!"'" [_])*) "'" { ast::Arg::Word(s) }
        //
        pub rule word() -> ast::Arg<'input> = word_quoted() / word_unquoted()


        // ## Variables
        //
        // For "free careting" to work correctly we must make certain assumptions about what
        // characters may appear in a variable name. We assume that a variable name consists only
        // of alphanumberic characters, percent (%), start (*), dash (-), and underscore (_).
        pub rule name() -> &'input str
            = n:$(['a'..='z' | 'A'..='Z' | '0'..='9' | '%' | '*' | '_' | '-']+) { n }
        //
        // The value of a variable is referenced with the notation:
        pub rule reference() -> ast::Arg<'input>
            = "$" v:name() { ast::Arg::Var(v) }


        // ## Lists
        //
        // The primary data structure is the list, which is a sequence of words. Parentheses are
        // used to group lists. The empty list is represented by ().
        pub rule arg() -> ast::Arg<'input> = reference() / word()
        pub rule list() -> ast::List<'input>
            = "(" x:(arg() ** _) ")" { x }
            / x:(arg() ** _) { x }


        // ## Statements
        //
        pub rule assignment() -> ast::Stmt<'input>
            = n:arg() _ "=" _ x:list() { ast::Stmt::Assignment(n, x) }

        pub rule command() -> ast::Stmt<'input>
            = n:arg() _ x:list() { ast::Stmt::Command(n, x) }

    }
}

#[cfg(test)]
mod tests {
    // use std::fs;
    use super::*;

    // from https://stackoverflow.com/questions/38183551
    macro_rules! word_vec {
        ($($x:expr),*) => (vec![$(ast::Arg::Word($x)),*]);
    }

    #[test]
    fn string() {
        assert_eq!(
            parser::word("''"),
            Ok(ast::Arg::Word(""))
        );
        assert_eq!(
            parser::word_quoted("'Hello world'"),
            Ok(ast::Arg::Word("Hello world"))
        );
    }

    #[test]
    fn reference() {
        assert!(parser::reference("$hello").is_ok());
        assert!(parser::reference("$%read").is_ok());
        assert!(parser::reference("$do_this").is_ok());
        assert!(parser::reference("$_private").is_ok());
        assert!(parser::reference("$a1").is_ok());

        assert!(parser::reference("$c$").is_err());
        assert!(parser::reference("$path/name").is_err());
    }

    #[test]
    fn list() {
        assert_eq!(parser::list("()"), Ok(vec![]));
        assert_eq!(parser::list("(1)"), Ok(word_vec!["1"]));
        assert_eq!(parser::list("(a b c)"), Ok(word_vec!["a", "b", "c"]));
        assert_eq!(
            parser::list("('Hello world')"),
            Ok(word_vec!["Hello world"])
        );
        assert_eq!(
            parser::list("(Hello 'Laurence de Bruxelles')"),
            Ok(word_vec!["Hello", "Laurence de Bruxelles"])
        );
    }

    #[test]
    fn list_unquoted() {
        assert_eq!(parser::list("2"), Ok(word_vec!["2"]));
        assert_eq!(parser::list("d e f"), Ok(word_vec!["d", "e", "f"]));
        assert_eq!(
            parser::list("'Hola todos'"),
            Ok(word_vec!["Hola todos"])
        );
        assert_eq!(
            parser::list("(Hola 'Lorenzo Anachury')"),
            Ok(word_vec!["Hola", "Lorenzo Anachury"])
        );
    }

    #[test]
    fn list_with_variable_references() {
        assert_eq!(
            parser::list("Hello $name"),
            Ok(vec![
                ast::Arg::Word("Hello"),
                ast::Arg::Var("name")
            ])
        );
    }

    #[test]
    fn list_common_argument_styles() {
        assert_eq!(
            parser::list("-h --verbose --var=value --output file.ext"),
            Ok(word_vec![
               "-h",
               "--verbose",
               "--var=value",
               "--output",
               "file.ext"
            ])
        );
    }

    #[test]
    fn assignment() {
        assert_eq!(
            parser::assignment("a = 1"),
            Ok(ast::Stmt::Assignment(ast::Arg::Word("a"), word_vec!["1"]))
        );
        assert_eq!(
            parser::assignment("list = (a b c)"),
            Ok(ast::Stmt::Assignment(
                ast::Arg::Word("list"),
                word_vec!["a", "b", "c"]
            ))
        );
        assert_eq!(
            parser::assignment("s = ('Hello world')"),
            Ok(ast::Stmt::Assignment(
                ast::Arg::Word("s"),
                word_vec!["Hello world"]
            ))
        );
        assert_eq!(
            parser::assignment("hello = Hello 'Laurence de Bruxelles'"),
            Ok(ast::Stmt::Assignment(
                ast::Arg::Word("hello"),
                word_vec!["Hello", "Laurence de Bruxelles"]
            ))
        );
        assert_eq!(
            parser::assignment("this = $that"),
            Ok(ast::Stmt::Assignment(
                ast::Arg::Word("this"),
                vec![ast::Arg::Var("that")]
            ))
        );
    }

    #[test]
    fn assignment_to_name_in_var() {
        assert_eq!(
            parser::assignment("$pointer = value"),
            Ok(ast::Stmt::Assignment(
                    ast::Arg::Var("pointer"),
                    word_vec!["value"]
            ))
        );
    }

    #[test]
    fn command() {
        assert_eq!(
            parser::command("%echo Hello $name"),
            Ok(ast::Stmt::Command(
                ast::Arg::Word("%echo"),
                vec![
                    ast::Arg::Word("Hello"),
                    ast::Arg::Var("name")
                ]
            ))
        );
    }

    #[test]
    fn command_in_var() {
        assert_eq!(
            parser::command("$command 1 2"),
            Ok(ast::Stmt::Command(
                    ast::Arg::Var("command"),
                    word_vec!["1", "2"]
            ))
        );
    }

    /*
    #[test]
    fn comments() {
        assert_eq!(parser::lines("# Hello World"), Ok(vec![1]));
        assert_eq!(parser::lines("# Hello World\n# 2nd line"), Ok(vec![1, 1]));
    }

    #[test]
    fn hello() {
        let script = fs::read_to_string("examples/hello.rcsh")
            .expect("could not read test file");

        println!("{}", script)
    }
    */
}
