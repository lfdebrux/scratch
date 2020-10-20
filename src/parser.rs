use peg;

pub mod ast {
    #[derive(Debug, PartialEq, Eq)]
    pub enum Arg {
        Var(String),
        Word(String),
    }

    pub type List = Vec<Arg>;

    #[derive(Debug, PartialEq, Eq)]
    pub enum Stmt {
        Assignment(String, List),
    }
}

peg::parser!{
    grammar rcsh_parser() for str {

        // ## Whitespace
        rule _() = quiet!{ [' ' | '\t'] }

        // TODO: replace String with string slices &str (need to think about lifetimes though)

        // ## Words
        //
        // The following characters have special meanings:
        rule chr() = !['#' | '$' | '|' | '&' | ';' | '(' | ')' | '<' | '>' | ' ' | '\t' | '\n'] [_]
        //
        // Special characters terminate words.
        pub rule word_unquoted() -> ast::Arg = w:$(chr()+) { ast::Arg::Word(w.to_string()) }
        //
        // The single quote prevents special treatment of any character other than itself.
        pub rule word_quoted() -> ast::Arg = "'" s:$((!"'" [_])*) "'" { ast::Arg::Word(s.to_string()) }
        //
        pub rule word() -> ast::Arg = word_quoted() / word_unquoted()


        // ## Variables
        //
        // For "free careting" to work correctly we must make certain assumptions about what
        // characters may appear in a variable name. We assume that a variable name consists only
        // of alphanumberic characters, percent (%), start (*), dash (-), and underscore (_).
        pub rule name() -> String
            = n:$(['a'..='z' | 'A'..='Z' | '0'..='9' | '%' | '*' | '_' | '-']+) { n.to_string() }
        //
        // The value of a variable is referenced with the notation:
        pub rule reference() -> ast::Arg
            = "$" v:name() { ast::Arg::Var(v) }


        // ## Lists
        //
        // The primary data structure is the list, which is a sequence of words. Parentheses are
        // used to group lists. The empty list is represented by ().
        pub rule arg() -> ast::Arg = reference() / word()
        pub rule list() -> ast::List
            = "(" x:(arg() ** _) ")" { x }
            / x:(arg() ** _) { x }


        // ## Statements
        //
        pub rule assignment() -> ast::Stmt
            = n:name() _ "=" _ x:list() { ast::Stmt::Assignment(n, x) }

        pub rule command() -> (String, ast::List)
            = n:name() _ x:list() { (n, x) }

    }
}

#[cfg(test)]
mod tests {
    // use std::fs;
    use super::*;

    // from https://stackoverflow.com/questions/38183551
    macro_rules! word_vec {
        ($($x:expr),*) => (vec![$(ast::Arg::Word($x.to_string())),*]);
    }

    #[test]
    fn string() {
        assert_eq!(rcsh_parser::word("''"), Ok(ast::Arg::Word(String::from(""))));
        assert_eq!(rcsh_parser::word_quoted("'Hello world'"), Ok(ast::Arg::Word(String::from("Hello world"))));
    }

    #[test]
    fn reference() {
        assert!(rcsh_parser::reference("$hello").is_ok());
        assert!(rcsh_parser::reference("$%read").is_ok());
        assert!(rcsh_parser::reference("$do_this").is_ok());
        assert!(rcsh_parser::reference("$_private").is_ok());
        assert!(rcsh_parser::reference("$a1").is_ok());

        assert!(rcsh_parser::reference("$c$").is_err());
        assert!(rcsh_parser::reference("$path/name").is_err());
    }

    #[test]
    fn list() {
        assert_eq!(rcsh_parser::list("()"), Ok(vec![]));
        assert_eq!(rcsh_parser::list("(1)"), Ok(word_vec!["1"]));
        assert_eq!(rcsh_parser::list("(a b c)"), Ok(word_vec!["a", "b", "c"]));
        assert_eq!(rcsh_parser::list("('Hello world')"), Ok(word_vec!["Hello world"]));
        assert_eq!(
            rcsh_parser::list("(Hello 'Laurence de Bruxelles')"),
            Ok(word_vec!["Hello", "Laurence de Bruxelles"])
        );
    }

    #[test]
    fn list_unquoted() {
        assert_eq!(rcsh_parser::list("2"), Ok(word_vec!["2"]));
        assert_eq!(rcsh_parser::list("d e f"), Ok(word_vec!["d", "e", "f"]));
        assert_eq!(rcsh_parser::list("'Hola todos'"), Ok(word_vec!["Hola todos"]));
        assert_eq!(
            rcsh_parser::list("(Hola 'Lorenzo Anachury')"),
            Ok(word_vec!["Hola", "Lorenzo Anachury"])
        );
    }

    #[test]
    fn list_with_variable_references() {
        assert_eq!(
            rcsh_parser::list("Hello $name"),
            Ok(vec![ast::Arg::Word("Hello".to_string()), ast::Arg::Var("name".to_string())])
        );
    }

    #[test]
    fn assignment() {
        assert_eq!(rcsh_parser::assignment("a = 1"), Ok(ast::Stmt::Assignment(String::from("a"), word_vec!["1"])));
        assert_eq!(rcsh_parser::assignment("list = (a b c)"), Ok(ast::Stmt::Assignment(String::from("list"), word_vec!["a", "b", "c"])));
        assert_eq!(rcsh_parser::assignment("s = ('Hello world')"), Ok(ast::Stmt::Assignment(String::from("s"), word_vec!["Hello world"])));
        assert_eq!(
            rcsh_parser::assignment("hello = Hello 'Laurence de Bruxelles'"),
            Ok(ast::Stmt::Assignment(String::from("hello"), word_vec!["Hello", "Laurence de Bruxelles"]))
        );
        assert_eq!(
            rcsh_parser::assignment("this = $that"),
            Ok(ast::Stmt::Assignment("this".to_string(), vec![ast::Arg::Var("that".to_string())]))
        );
    }

    /*
    #[test]
    fn comments() {
        assert_eq!(rcsh_parser::lines("# Hello World"), Ok(vec![1]));
        assert_eq!(rcsh_parser::lines("# Hello World\n# 2nd line"), Ok(vec![1, 1]));
    }

    #[test]
    fn hello() {
        let script = fs::read_to_string("examples/hello.rcsh")
            .expect("could not read test file");

        println!("{}", script)
    }
    */
}
