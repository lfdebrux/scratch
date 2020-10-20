use peg;

pub mod ast {
    #[derive(Debug, PartialEq, Eq)]
    pub enum Token {
        Word(String),
        Name(String),
    }

    pub type List = Vec<Token>;
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
        pub rule word_unquoted() -> ast::Token = w:$(chr()+) { ast::Token::Word(w.to_string()) }
        //
        // The single quote prevents special treatment of any character other than itself.
        pub rule word_quoted() -> ast::Token = "'" s:$((!"'" [_])*) "'" { ast::Token::Word(s.to_string()) }
        //
        pub rule word() -> ast::Token = word_quoted() / word_unquoted()


        // ## Variables
        //
        // For "free careting" to work correctly we must make certain assumptions about what
        // characters may appear in a variable name. We assume that a variable name consists only
        // of alphanumberic characters, percent (%), start (*), dash (-), and underscore (_).
        pub rule name() -> ast::Token
            = n:$(['a'..='z' | 'A'..='Z' | '0'..='9' | '%' | '*' | '_' | '-']+) { ast::Token::Name(n.to_string()) }
        //
        // The value of a variable is referenced with the notation:
        pub rule reference() -> ast::Token
            = "$" v:name() { v }


        // ## Lists
        //
        // The primary data structure is the list, which is a sequence of words. Parentheses are
        // used to group lists. The empty list is represented by ().
        pub rule token() -> ast::Token = reference() / word()
        pub rule list() -> ast::List
            = "(" x:(token() ** _) ")" { x }
            / x:(token() ** _) { x }


        // statements
        pub rule assignment() -> (ast::Token, ast::List)
            = n:name() _ "=" _ x:list() { (n, x) }

        pub rule command() -> (ast::Token, ast::List)
            = n:name() _ x:list() { (n, x) }

    }
}

#[cfg(test)]
mod tests {
    // use std::fs;
    use super::*;

    // from https://stackoverflow.com/questions/38183551
    macro_rules! word_vec {
        ($($x:expr),*) => (vec![$(ast::Token::Word($x.to_string())),*]);
    }

    #[test]
    fn string() {
        assert_eq!(rcsh_parser::word("''"), Ok(ast::Token::Word(String::from(""))));
        assert_eq!(rcsh_parser::word_quoted("'Hello world'"), Ok(ast::Token::Word(String::from("Hello world"))));
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
            Ok(vec![ast::Token::Word("Hello".to_string()), ast::Token::Name("name".to_string())])
        );
    }

    #[test]
    fn assignment() {
        assert_eq!(rcsh_parser::assignment("a = 1"), Ok((ast::Token::Name(String::from("a")), word_vec!["1"])));
        assert_eq!(rcsh_parser::assignment("list = (a b c)"), Ok((ast::Token::Name(String::from("list")), word_vec!["a", "b", "c"])));
        assert_eq!(rcsh_parser::assignment("s = ('Hello world')"), Ok((ast::Token::Name(String::from("s")), word_vec!["Hello world"])));
        assert_eq!(
            rcsh_parser::assignment("hello = Hello 'Laurence de Bruxelles'"),
            Ok((ast::Token::Name(String::from("hello")), word_vec!["Hello", "Laurence de Bruxelles"]))
        );
        assert_eq!(
            rcsh_parser::assignment("this = $that"),
            Ok((ast::Token::Name("this".to_string()), vec![ast::Token::Name("that".to_string())]))
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
