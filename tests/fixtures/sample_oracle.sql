CREATE TABLE hr.employees (
    id NUMBER(10) NOT NULL,
    name VARCHAR2(100),
    hire_date DATE,
    salary NUMBER(10,2),
    dept_id NUMBER(10),
    CONSTRAINT pk_emp PRIMARY KEY (id),
    CONSTRAINT fk_emp_dept FOREIGN KEY (dept_id) REFERENCES hr.departments(id)
);

CREATE TABLE hr.departments (
    id NUMBER(10) NOT NULL,
    dept_name VARCHAR2(100),
    CONSTRAINT pk_dept PRIMARY KEY (id)
);

CREATE SEQUENCE hr.emp_seq START WITH 1 INCREMENT BY 1;

CREATE OR REPLACE TRIGGER hr.trg_emp_bi
BEFORE INSERT ON hr.employees
FOR EACH ROW
BEGIN
    :NEW.id := hr.emp_seq.NEXTVAL;
END;
/

CREATE OR REPLACE VIEW hr.active_employees AS
SELECT * FROM hr.employees WHERE hire_date > SYSDATE - 365;

CREATE OR REPLACE PROCEDURE hr.update_salary(p_id NUMBER, p_amount NUMBER) AS
BEGIN
    UPDATE hr.employees SET salary = p_amount WHERE id = p_id;
    COMMIT;
END;
/

CREATE OR REPLACE FUNCTION hr.get_dept_count(p_dept_id NUMBER) RETURN NUMBER AS
    v_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM hr.employees WHERE dept_id = p_dept_id;
    RETURN v_count;
END;
/

CREATE SYNONYM hr.emp FOR hr.employees;

CREATE INDEX hr.idx_emp_dept ON hr.employees(dept_id);

CREATE MATERIALIZED VIEW hr.dept_summary AS
SELECT dept_id, COUNT(*) as emp_count, AVG(salary) as avg_salary
FROM hr.employees
GROUP BY dept_id;
