<schema xmlns="http://purl.oclc.org/dsdl/schematron">

  <!--
    SchematronRules.sch
    Skeleton Schematron covering each rule in `AE Validation Rules.txt`.

    Notes / assumptions:
    - Element and attribute names are assumed from the AE spec text (SWC, Port,
      SENDER-RECEIVER-INTERFACE, Provider, Required, Runnable, Event, DataAccess,
      SoCs, ECUs, Chiplet, Generic_Hardware, Hwip, CPU_Cluster, HwSwMapping, etc.).
    - Where XPath 1.0 can express the rule (uniqueness, counts, existence within
      a document) a concrete assert is provided. Where the rule requires
      filesystem checks, XPath 2.0 regex (matches()) or complex graph traversal
      that depends on actual attribute names, a TODO placeholder assert is
      inserted and marked with IMPLEMENTATION-NOTE so you can refine it.
    - This file is intentionally conservative (placeholder asserts use test="true()"
      so they do not produce false failures). Replace placeholders with real
      XPath tests adjusted to your XML element/attribute names to enable checks.
  -->

  <!-- SWC Validations (Rules 1-20) -->
  <pattern id="swc-validations">

    <!-- Rule 1: Each SWC has a unique name. -->
    <rule context="//APPLICATION-SW-COMPONENT-TYPE">
      <assert test="not(SHORT-NAME/@name = preceding::APPLICATION-SW-COMPONENT-TYPE/SHORT-NAME/@name)">
        Each APPLICATION-SW-COMPONENT-TYPE must have a unique SHORT-NAME/@name within the document.
      </assert>
    </rule>

    <!-- Rules 2, 3, 5: P-PORT-PROTOTYPE validations (combined due to same context) -->
    <rule context="//APPLICATION-SW-COMPONENT-TYPE/PORTS/P-PORT-PROTOTYPE">
      <!-- Rule 2: Each Port has a unique name (within its SWC) -->
      <assert test="not(SHORT-NAME/@name = preceding-sibling::P-PORT-PROTOTYPE/SHORT-NAME/@name)">
        Each P-PORT-PROTOTYPE must have a unique SHORT-NAME/@name within its SWC.
      </assert>

      <!-- Rule 3: Each Port is connected to a valid Sender-Receiver Interface. -->
      <assert test="string-length(PROVIDED-INTERFACE-TREF/@DEST) &gt; 0 and contains(PROVIDED-INTERFACE-TREF/@DEST, '/')">
        Provided port must have a non-empty PROVIDED-INTERFACE-TREF/@DEST that looks like a path. (Use Python for strict resolution against SRI SHORT-NAME.)
      </assert>

      <!-- Rule 5: Each Provider port is connected to only one Data Write Access. -->
      <assert test="count(//DATA-WRITE-ACCESS[.//PORT-PROTOTYPE-REF/@DEST]) &gt;= 1">
        Each Provided port should be referenced by a DATA-WRITE-ACCESS with a PORT-PROTOTYPE-REF/@DEST. Use Python to ensure it references this specific port and exactly once.
      </assert>
    </rule>

    <!-- Rules 3, 4: R-PORT-PROTOTYPE validations (combined due to same context) -->
    <rule context="//APPLICATION-SW-COMPONENT-TYPE/PORTS/R-PORT-PROTOTYPE">
      <!-- Rule 3: Each Port is connected to a valid Sender-Receiver Interface (R-PORT). -->
      <!-- Schematron: Checks that DEST is non-empty and looks like a path (contains '/') -->
      <!-- Python: Checks that the referenced interface actually exists in the model -->
      <assert test="string-length(REQUIRED-INTERFACE-TREF/@DEST) &gt; 0 and contains(REQUIRED-INTERFACE-TREF/@DEST, '/')">
        Required port must have a non-empty REQUIRED-INTERFACE-TREF/@DEST that looks like a path. (Use Python for strict resolution.)
      </assert>

      <!-- Rule 4: Each Required port is connected to only one Data Read Access. -->
      <!-- Schematron: Basic check that at least one DATA-READ-ACCESS exists in the document -->
      <!-- Python: Full check that this specific R-PORT is referenced by EXACTLY one DATA-READ-ACCESS (not 0, not 2+) -->
      <assert test="count(//DATA-READ-ACCESS[.//PORT-PROTOTYPE-REF/@DEST]) &gt;= 1">
        Each Required port should be referenced by a DATA-READ-ACCESS with a PORT-PROTOTYPE-REF/@DEST. Use Python to ensure it references this exact port and that there's exactly one.
      </assert>
    </rule>

  <!-- Rule 7: Runnable name valid against simplified C-style rule (no spaces) -->
    <rule context="//RUNNABLE-ENTITY/SHORT-NAME">
      <assert test="string-length(normalize-space(@name)) &gt; 0 and not(contains(@name, ' '))">
        Runnable SHORT-NAME/@name must be non-empty and contain no spaces. For full C-identifier rules (start with letter/underscore and only [A-Za-z0-9_], not a C keyword), use the Python validator.
      </assert>
    </rule>

  <!-- Rule 8: Each Runnable has at least one Event. -->
    <!-- In this model, EVENTS are siblings of RUNNABLES under SWC-INTERNAL-BEHAVIOR.
         We consider a Runnable to have an Event if there exists a TIMING-EVENT or
         DATA-RECEIVED-EVENT whose START-ON-EVENT-REF/@DEST ends with '/' + runnable SHORT-NAME.
         XPath 1.0 does not have ends-with(), so we use a substring() technique. -->
    <rule context="//RUNNABLE-ENTITY">
      <!-- Rule 8: Each Runnable has at least one Event -->
      <assert test="count(ancestor::SWC-INTERNAL-BEHAVIOR/EVENTS/*[self::TIMING-EVENT or self::DATA-RECEIVED-EVENT][
                        substring(START-ON-EVENT-REF/@DEST,
                                  string-length(START-ON-EVENT-REF/@DEST) -
                                  string-length(concat('/', current()/SHORT-NAME/@name)) + 1
                        ) = concat('/', current()/SHORT-NAME/@name)
                      ]) &gt;= 1">
        Rule 8 violated: Each RUNNABLE-ENTITY must be referenced by at least one Event in the same SWC-INTERNAL-BEHAVIOR.
      </assert>

      <!-- Rule 14: Runnable can't have Data Read and Write access to the same port -->
      <assert test="not(DATA-READ-ACCESS//PORT-PROTOTYPE-REF/@DEST = DATA-WRITE-ACCESS//PORT-PROTOTYPE-REF/@DEST)">
        Rule 14 violated: Runnable must not reference the same PORT-PROTOTYPE-REF/@DEST in both DATA-READ-ACCESS and DATA-WRITE-ACCESS (partial check; Python validator performs complete SRI resolution).
      </assert>
    </rule>

  <!-- Rule 9: Each Runnable is mapped to a valid Cpu Core. -->
    <!-- Check Core mappings in HW-SW mapping (Core-Runnable-Mapping) and CPU core (Core-runnable-Mapping DEST) reference an existing RUNNABLE-ENTITY SHORT-NAME. -->
    <rule context="//Core-Runnable-Mapping | //Core-runnable-Mapping">
      <!-- Conservative: ensure RunnableRef or DEST is present and looks like an absolute path. Use Python to strictly resolve to RUNNABLE-ENTITY names. -->
      <assert test="(string-length(@RunnableRef) &gt; 0 and starts-with(@RunnableRef, '/')) or (string-length(@DEST) &gt; 0 and starts-with(@DEST, '/'))">
        Core mapping should include a RunnableRef or DEST path (starting with '/'). Use Python for strict resolution to RUNNABLE-ENTITY.
      </assert>
    </rule>

    <!-- Rule 9 (existence-only, Schematron): Each Runnable has at least one Core mapping. -->
    <!-- We assert that for each RUNNABLE-ENTITY there exists at least one Core-Runnable-Mapping
         whose @RunnableRef ends with '/' + the runnable's SHORT-NAME. XPath 1.0 lacks ends-with(),
         so we use the substring() technique as in Rule 8. Full correctness (ClusterRef resolution,
         CoreId bounds, and robust path matching) remains in Python. -->
    <rule context="//RUNNABLE-ENTITY">
      <assert test="count(//Core-Runnable-Mapping[@RunnableRef =
                        concat('/'
                              , ancestor::APPLICATION-SW-COMPONENT-TYPE/SHORT-NAME/@name
                              , '/'
                              , ancestor::SWC-INTERNAL-BEHAVIOR/SHORT-NAME/@name
                              , '/'
                              , SHORT-NAME/@name
                        )
                      ]) &gt;= 1">
        Each RUNNABLE-ENTITY must be referenced by at least one Core-Runnable-Mapping (existence-only). Use Python to validate mapping correctness (ClusterRef/CoreId bounds and exact reference resolution).
      </assert>
    </rule>

  <!-- Rule 10: Each Runnable is mapped to only one Cpu Core. -->
    <rule context="//RUNNABLE-ENTITY">
      <!-- Non-failing informational report: detailed per-runnable mapping uniqueness is handled in Python. -->
      <report test="count(//Core-Runnable-Mapping | //Core-runnable-Mapping) = 0">
        IMPLEMENTATION-NOTE: No Core-Runnable mapping entries found. Runnable-to-core uniqueness is validated by the Python stage.
      </report>
    </rule>

    <!-- Schematron hint for Rule 10: warn on duplicate RunnableRef within the same HW-SW-MAPPING block (non-blocking). -->
    <rule context="//HW-SW-MAPPING/Core-Runnable-Mapping">
      <report test="@RunnableRef = preceding-sibling::Core-Runnable-Mapping/@RunnableRef">
        Hint (Rule 10): Duplicate Core-Runnable-Mapping for RunnableRef '<value-of select="@RunnableRef"/>' within the same HW-SW-MAPPING. Each runnable should be mapped only once.
      </report>
    </rule>

  <!-- Rule 11: Each Data Access has a unique name within the Runnable. -->
    <!-- In the XSD, Data Access entries are modeled as VARIABLE-ACCESS under
         DATA-READ-ACCESS or DATA-WRITE-ACCESS inside a RUNNABLE-ENTITY.
         Each VARIABLE-ACCESS has a SHORT-NAME/@name. Names must be unique
         within the containing RUNNABLE-ENTITY across both read and write. -->
    <rule context="//RUNNABLE-ENTITY//VARIABLE-ACCESS/SHORT-NAME">
      <assert test="count(preceding::SHORT-NAME[parent::VARIABLE-ACCESS
                                and ancestor::RUNNABLE-ENTITY = current()/ancestor::RUNNABLE-ENTITY
                                and @name = current()/@name]) = 0">
        Each Data Access name (VARIABLE-ACCESS/SHORT-NAME/@name) must be unique within its RUNNABLE-ENTITY (across reads and writes).
      </assert>
    </rule>

  <!-- Rule 12: Each Data Access is connected to a valid port -->
    <!-- PORT-PROTOTYPE-REF elements carry DEST attributes pointing to port prototypes; ensure the referenced port exists as a P-PORT-PROTOTYPE or R-PORT-PROTOTYPE SHORT-NAME. -->
    <rule context="//PORT-PROTOTYPE-REF">
      <!-- Check 1: DEST must be present and look like an absolute path -->
      <assert test="string-length(@DEST) &gt; 0 and starts-with(@DEST, '/')">
        PORT-PROTOTYPE-REF/@DEST must be present and look like an absolute path (start with '/').
      </assert>

      <!-- Check 2: Verify the port exists in the same SWC.
           PORT-PROTOTYPE-REF/@DEST format is typically "/SWCName/PortName".
           We extract the port name (last segment) and verify it matches a P-PORT or R-PORT SHORT-NAME
           in the ancestor SWC. XPath 1.0 approach: check if there exists a port whose full path
           matches the DEST by constructing the expected path from ancestor SWC and comparing. -->
      <assert test="count(ancestor::APPLICATION-SW-COMPONENT-TYPE//P-PORT-PROTOTYPE[
                      concat('/', ancestor::APPLICATION-SW-COMPONENT-TYPE/SHORT-NAME/@name, '/', SHORT-NAME/@name) = current()/@DEST
                    ]) +
                    count(ancestor::APPLICATION-SW-COMPONENT-TYPE//R-PORT-PROTOTYPE[
                      concat('/', ancestor::APPLICATION-SW-COMPONENT-TYPE/SHORT-NAME/@name, '/', SHORT-NAME/@name) = current()/@DEST
                    ]) &gt;= 1">
        PORT-PROTOTYPE-REF/@DEST '<value-of select="@DEST"/>' does not resolve to an existing P-PORT-PROTOTYPE or R-PORT-PROTOTYPE in the SWC. Each data access must reference a valid declared port.
      </assert>
    </rule>

  <!-- Rule 13: Each Data Access is connected to a valid Target Data -->
    <rule context="//TARGET-DATA-PROTOTYPE-REF">
      <!-- Check 1: DEST must be present and look like an absolute path -->
      <assert test="string-length(@DEST) &gt; 0 and starts-with(@DEST, '/')">
        TARGET-DATA-PROTOTYPE-REF/@DEST must be present and look like an absolute path (start with '/').
      </assert>

      <!-- Check 2: Verify the target data exists in a declared SRI.
           TARGET-DATA-PROTOTYPE-REF/@DEST format is typically "/InterfaceName/DataElementName".
           We extract the data element name (last segment) and verify it matches a VARIABLE-DATA-PROTOTYPE
           SHORT-NAME in a SENDER-RECEIVER-INTERFACE. XPath 1.0 approach: check if there exists a data element
           whose full path matches the DEST by constructing the expected path and comparing. -->
      <assert test="count(//SENDER-RECEIVER-INTERFACE//VARIABLE-DATA-PROTOTYPE[
                      concat('/', ancestor::SENDER-RECEIVER-INTERFACE/SHORT-NAME/@name, '/', SHORT-NAME/@name) = current()/@DEST
                    ]) &gt;= 1">
        TARGET-DATA-PROTOTYPE-REF/@DEST '<value-of select="@DEST"/>' does not resolve to an existing VARIABLE-DATA-PROTOTYPE in any SENDER-RECEIVER-INTERFACE. Each data access must reference a valid declared data element.
      </assert>
    </rule>

    <!-- Combined Event validations (Rules 15, 16, 17) -->
    <!-- Scope to SWC events only to avoid applying SWC assumptions to Generic_Hardware events. -->
    <rule context="//SWC-INTERNAL-BEHAVIOR//TIMING-EVENT | //SWC-INTERNAL-BEHAVIOR//DATA-RECEIVED-EVENT | //SWC-INTERNAL-BEHAVIOR//TRIGGER-EVENT">
      <!-- Variables for Rule 17 - must be declared BEFORE any assertions -->
      <let name="ref_path" value="START-ON-EVENT-REF/@DEST"/>
      <!-- Extract runnable name as the last path segment after two slashes: '/SWC/Behavior/Runnable' -->
      <let name="ref_after1" value="substring-after($ref_path, '/')"/>
      <let name="ref_after2" value="substring-after($ref_after1, '/')"/>
      <let name="runnable_name" value="substring-after($ref_after2, '/')"/>
      <!-- Extract SWC and Behavior segments from DEST -->
      <let name="dest_swc" value="substring-before($ref_after1, '/')"/>
      <let name="dest_behav" value="substring-before($ref_after2, '/')"/>
      <!-- Current context SWC and Behavior names -->
      <let name="curr_swc" value="ancestor::APPLICATION-SW-COMPONENT-TYPE/SHORT-NAME/@name"/>
      <let name="curr_behav" value="ancestor::SWC-INTERNAL-BEHAVIOR/SHORT-NAME/@name"/>

  <!-- Variables for Rule 18 (Custom Behavior) -->
  <let name="cb_name" value="CUSTOM-BEHAVIOR-REF/@DEST"/>      <!-- Rule 15: Each Event has a unique name within the same EVENTS container -->
      <assert test="not(SHORT-NAME/@name = preceding-sibling::*/SHORT-NAME/@name)">
        Rule 15 violated: Event SHORT-NAME/@name '<value-of select="SHORT-NAME/@name"/>' is not unique. Each event must have a unique name within the same runnable.
      </assert>

      <!-- Rule 16: Each Event name is valid against C variable naming rules (basic check: no spaces) -->
      <assert test="string-length(normalize-space(SHORT-NAME/@name)) &gt; 0 and not(contains(SHORT-NAME/@name, ' '))">
        Rule 16 violated (partial): Event SHORT-NAME/@name '<value-of select="SHORT-NAME/@name"/>' contains spaces or is empty. Full C identifier validation (regex, keywords) is performed by Python.
      </assert>

      <!-- Rule 17: Each Event is connected to a valid Runnable -->
      <!-- Check A: DEST must exist and be non-empty -->
      <assert test="START-ON-EVENT-REF and string-length(normalize-space($ref_path)) &gt; 0">
        Rule 17 violated: Each Event should be connected to a valid Runnable. Event '<value-of select="SHORT-NAME/@name"/>' must include a non-empty START-ON-EVENT-REF/@DEST.
      </assert>

      <!-- Check B1: If DEST is provided, SWC in DEST must match current SWC -->
      <assert test="not(START-ON-EVENT-REF) or string-length(normalize-space($ref_path)) = 0 or ($dest_swc = $curr_swc)">
        Rule 17 violated: Each Event should be connected to a valid Runnable. Event '<value-of select="SHORT-NAME/@name"/>' references SWC '<value-of select="$dest_swc"/>' but is defined under SWC '<value-of select="$curr_swc"/>' (path: '<value-of select="$ref_path"/>').
      </assert>

      <!-- Check B2: If DEST is provided, Behavior in DEST must match current Behavior -->
      <assert test="not(START-ON-EVENT-REF) or string-length(normalize-space($ref_path)) = 0 or ($dest_behav = $curr_behav)">
        Rule 17 violated: Each Event should be connected to a valid Runnable. Event '<value-of select="SHORT-NAME/@name"/>' references Behavior '<value-of select="$dest_behav"/>' but is defined under Behavior '<value-of select="$curr_behav"/>' (path: '<value-of select="$ref_path"/>').
      </assert>

      <!-- Check B3: The referenced runnable name must exist in the same Behavior (uniqueness handled elsewhere) -->
      <assert test="not(START-ON-EVENT-REF) or string-length(normalize-space($ref_path)) = 0 or count(ancestor::SWC-INTERNAL-BEHAVIOR/RUNNABLES/RUNNABLE-ENTITY[SHORT-NAME/@name = $runnable_name]) &gt;= 1">
        Rule 17 violated: Each Event should be connected to a valid Runnable. Event '<value-of select="SHORT-NAME/@name"/>' references runnable name '<value-of select="$runnable_name"/>' via START-ON-EVENT-REF/@DEST='<value-of select="$ref_path"/>', but no such runnable exists in this SWC-Internal-Behavior.
      </assert>

      <!-- Rule 18: Each Event is connected to a valid behavior if exists. -->
      <!-- 18.A: Non-empty when present -->
      <assert test="not(CUSTOM-BEHAVIOR-REF) or string-length(normalize-space($cb_name)) &gt; 0">
        Rule 18 violated: Each Event should be connected to a valid behavior if exists. If present, CUSTOM-BEHAVIOR-REF/@DEST must be non-empty.
      </assert>

      <!-- Rule 19: Each Data-Received Event is connected to a valid Data Read Access. -->
      <!-- 19.A: If this is a DATA-RECEIVED-EVENT, at least one TARGET-DATA-ELEMENT-REF must exist -->
      <assert test="not(self::DATA-RECEIVED-EVENT) or count(DATA-IREF/TARGET-DATA-ELEMENT-REF) &gt;= 1">
        Rule 19 violated: Each Data-Received Event must have at least one TARGET-DATA-ELEMENT-REF in DATA-IREF.
      </assert>

      <!-- 18.B: Must reference an existing SWC-CUSTOM-BEHAVIOR by SHORT-NAME -->
      <assert test="not(CUSTOM-BEHAVIOR-REF) or count(//SWC-CUSTOM-BEHAVIOR/SHORT-NAME[@name = $cb_name]) &gt;= 1">
        Rule 18 violated: Each Event should be connected to a valid behavior if exists. CUSTOM-BEHAVIOR-REF/@DEST='<value-of select="$cb_name"/>' does not reference any SWC-CUSTOM-BEHAVIOR SHORT-NAME.
      </assert>
    </rule>


  <!-- Rule 19 (per-reference validation): Each TARGET-DATA-ELEMENT-REF in a Data-Received Event must be valid -->
    <rule context="//DATA-RECEIVED-EVENT//TARGET-DATA-ELEMENT-REF">
      <!-- Variables to parse the path for THIS specific reference -->
      <let name="dre_path" value="@DEST"/>
      <let name="dre_after1" value="substring-after($dre_path, '/')"/>
      <let name="dre_after2" value="substring-after($dre_after1, '/')"/>
      <let name="dre_after3" value="substring-after($dre_after2, '/')"/>
      <let name="dre_swc" value="substring-before($dre_after1, '/')"/>
      <let name="dre_behav" value="substring-before($dre_after2, '/')"/>
      <let name="dre_run" value="substring-before($dre_after3, '/')"/>
      <let name="dre_var" value="substring-after($dre_after3, '/')"/>

      <!-- Get context from the parent event -->
      <let name="event_name" value="ancestor::DATA-RECEIVED-EVENT/SHORT-NAME/@name"/>
      <let name="curr_swc" value="ancestor::APPLICATION-SW-COMPONENT-TYPE/SHORT-NAME/@name"/>
      <let name="curr_behav" value="ancestor::SWC-INTERNAL-BEHAVIOR/SHORT-NAME/@name"/>
      <let name="ref_path" value="ancestor::DATA-RECEIVED-EVENT/START-ON-EVENT-REF/@DEST"/>
      <let name="ref_after1" value="substring-after($ref_path, '/')"/>
      <let name="ref_after2" value="substring-after($ref_after1, '/')"/>
      <let name="runnable_name" value="substring-after($ref_after2, '/')"/>

      <!-- 19.B: @DEST must be non-empty and look like a path -->
      <assert test="string-length(normalize-space($dre_path)) &gt; 0 and contains($dre_path, '/')">
        Rule 19 violated: TARGET-DATA-ELEMENT-REF/@DEST must be non-empty and contain '/'. Event '<value-of select="$event_name"/>' has an invalid reference.
      </assert>

      <!-- 19.C: DEST path must have 4 non-empty segments: /SWC/Behavior/Runnable/Variable -->
      <assert test="string-length($dre_swc) &gt; 0 and string-length($dre_behav) &gt; 0 and string-length($dre_run) &gt; 0 and string-length($dre_var) &gt; 0">
        Rule 19 violated: TARGET-DATA-ELEMENT-REF/@DEST='<value-of select="$dre_path"/>' is malformed. Expected /&lt;SWC&gt;/&lt;Behavior&gt;/&lt;Runnable&gt;/&lt;Variable&gt;. Event '<value-of select="$event_name"/>'.
      </assert>

      <!-- 19.D: SWC, Behavior, and Runnable in DEST must match the event's context and START-ON-EVENT-REF -->
      <assert test="$dre_swc = $curr_swc and $dre_behav = $curr_behav and $dre_run = $runnable_name">
        Rule 19 violated: TARGET-DATA-ELEMENT-REF path ('<value-of select="$dre_path"/>') must reference the same SWC ('<value-of select="$curr_swc"/>'), Behavior ('<value-of select="$curr_behav"/>'), and Runnable ('<value-of select="$runnable_name"/>') as the event's START-ON-EVENT-REF. Event '<value-of select="$event_name"/>'.
      </assert>

      <!-- 19.E: Variable must exist under DATA-READ-ACCESS of the referenced Runnable -->
      <assert test="count(ancestor::SWC-INTERNAL-BEHAVIOR/RUNNABLES/RUNNABLE-ENTITY[SHORT-NAME/@name = $runnable_name]/DATA-READ-ACCESS//VARIABLE-ACCESS[SHORT-NAME/@name = $dre_var]) &gt;= 1">
        Rule 19 violated: Variable '<value-of select="$dre_var"/>' not found under DATA-READ-ACCESS of runnable '<value-of select="$runnable_name"/>'. Event '<value-of select="$event_name"/>'.
      </assert>
    </rule>

    <!-- Rule 20: Each Timing Event has valid period value.
         NOTE: This rule is fully enforced by XSD schema validation.
         XSD checks: PERIOD element exists, value/unit attributes are required,
         value is unsignedLong, unit is one of s/ms/us/ns.
         No Schematron validation needed. -->

    <rule context="//TIMING-EVENT">
      <assert test="number(PERIOD/@value) &gt; 0">Timing Event PERIOD/@value must be numeric and positive.</assert>
      <!-- Timing Event Period must be at least 10ms (convert to ms for comparison) -->
      <assert test="
        (PERIOD/@unit = 'ms' and number(PERIOD/@value) &gt;= 10) or
        (PERIOD/@unit = 's' and number(PERIOD/@value) &gt;= 0.01) or
        (PERIOD/@unit = 'us' and number(PERIOD/@value) &gt;= 10000) or
        (PERIOD/@unit = 'ns' and number(PERIOD/@value) &gt;= 10000000) or
        (not(PERIOD/@unit) and number(PERIOD/@value) &gt;= 10)
      ">
        Timing Event Period must be at least 10ms. Found: <value-of select="PERIOD/@value"/> <value-of select="PERIOD/@unit"/>.
      </assert>
    </rule>

  <!-- Rule 6: Each Runnable has a unique name (global check). -->
    <rule context="//RUNNABLE-ENTITY">
      <assert test="not(SHORT-NAME/@name = preceding-sibling::RUNNABLE-ENTITY/SHORT-NAME/@name)">
        Rule 6 violated: Duplicate RUNNABLE-ENTITY SHORT-NAME/@name found among siblings: '<value-of select="SHORT-NAME/@name"/>'
      </assert>
    </rule>
  </pattern>

  <!-- Custom Behaviors (Rules 21-26) -->
  <pattern id="custom-behaviors">
    <!-- Rule 21: Each Custom Behavior has a unique name. -->
    <rule context="//CustomBehavior">
      <assert test="not(@name = preceding::CustomBehavior/@name)">Each Custom Behavior must have a unique @name.</assert>
    </rule>

    <!-- Rule 22: Each Read Operation has a valid Data Access reference. -->
    <rule context="//SWC-CUSTOM-BEHAVIOR//READ">
      <assert test="string-length(IREF/@DEST) &gt; 0">READ IREF must include a non-empty DEST. Use Python to verify it references a DATA-READ-ACCESS VARIABLE-ACCESS.
      </assert>
    </rule>

    <!-- Rule 23: Each Write Operation has a valid Data Access reference. -->
    <rule context="//SWC-CUSTOM-BEHAVIOR//WRITE">
      <assert test="string-length(IREF/@DEST) &gt; 0">WRITE IREF must include a non-empty DEST. Use Python to verify it references a DATA-WRITE-ACCESS VARIABLE-ACCESS.
      </assert>
    </rule>

    <!-- ############## Rule 24: All Read and Write Operations have Data Access reference to same Runnable. -->
    <rule context="//SWC-CUSTOM-BEHAVIOR">
      <assert test="true()">IMPLEMENTATION-NOTE: ensure all READ/WRITE IREFs in this SWC-CUSTOM-BEHAVIOR reference DataAccess within the same Runnable. This requires normalizing IREF paths and comparing their runnable segments; implement with XPath 2.0 or in Python if needed.</assert>
    </rule>

    <!-- ############## Rule 25: Each Custom Operation has valid inputs. -->

    <!-- Rule 25a & 25b: CUSTOM-OPERATION validation (format + non-empty attributes) -->
    <rule context="//CUSTOM-OPERATION">
      <assert test="@functionPrototype and string-length(normalize-space(@functionPrototype)) &gt; 0">
        CUSTOM-OPERATION must have a non-empty functionPrototype attribute.
      </assert>
      <assert test="starts-with(normalize-space(@functionPrototype), 'void ') and contains(@functionPrototype, '(void)')">
        CUSTOM-OPERATION functionPrototype must follow the format "void func_name(void)".
      </assert>
      <assert test="@headerFile and string-length(normalize-space(@headerFile)) &gt; 0">
        CUSTOM-OPERATION must have a non-empty headerFile attribute.
      </assert>
      <assert test="@includesDir and string-length(normalize-space(@includesDir)) &gt; 0">
        CUSTOM-OPERATION must have a non-empty includesDir attribute.
      </assert>
      <assert test="@sourcesDir and string-length(normalize-space(@sourcesDir)) &gt; 0">
        CUSTOM-OPERATION must have a non-empty sourcesDir attribute.
      </assert>
    </rule>

    <!-- Note: AI/ML operations (CONVOLUTION, MAX-POOL, etc.) have numeric attributes validated by XSD.
         Rule 25 logical validation only applies to CUSTOM-OPERATION format requirements. -->

    <!-- Rule 26: Latency operation not allowed in Custom Behavior. -->
    <!-- Use LATENCY nodes under SWC-CUSTOM-BEHAVIOR as context and force fail -->
    <rule context="//SWC-CUSTOM-BEHAVIOR//LATENCY">
      <assert test="false()">LATENCY operation is not allowed inside SWC-CUSTOM-BEHAVIOR.</assert>
    </rule>
  </pattern>

  <!-- Sender Receiver Interface (SRI) (Rules 27-35) -->
  <pattern id="sri-validations">
    <!-- Rules 27, 29, 30, 32: Combined into one context for //SENDER-RECEIVER-INTERFACE -->
    <rule context="//SENDER-RECEIVER-INTERFACE">
      <let name="sri_name" value="SHORT-NAME/@name"/>
      <let name="sri_ref" value="concat('/', $sri_name)"/>
  <let name="provider_count" value="count(//P-PORT-PROTOTYPE[substring-after(PROVIDED-INTERFACE-TREF/@DEST, '/') = $sri_name])"/>
  <let name="required_count" value="count(//R-PORT-PROTOTYPE[substring-after(REQUIRED-INTERFACE-TREF/@DEST, '/') = $sri_name])"/>

      <!-- Rule 27: Each Sender-Receiver interface has a unique name. -->
      <assert test="not($sri_name = preceding::SENDER-RECEIVER-INTERFACE/SHORT-NAME/@name)">
        Rule 27 violated: Each SRI must have a unique SHORT-NAME. Duplicate found: '<value-of select="$sri_name"/>'.
      </assert>

      <!-- Rule 29: Each Sender-Receiver interface has only one Provider Port. -->
      <assert test="$provider_count = 1">
        Rule 29 violated: SRI '<value-of select="$sri_name"/>' has <value-of select="$provider_count"/> provider port(s), expected exactly 1.
      </assert>

      <!-- Rule 30: Each Sender-Receiver interface has only one Required Port. -->
      <assert test="$required_count = 1">
        Rule 30 violated: SRI '<value-of select="$sri_name"/>' has <value-of select="$required_count"/> required port(s), expected exactly 1.
      </assert>

  <!-- Rule 32: (Removed from Schematron; enforced in Python only) -->
    </rule>

    <!-- Rule 28: Each Sender-Receiver interface name is valid against C variable naming rules (simplified). -->
    <!-- Target SHORT-NAME directly for more reliable attribute evaluation -->
    <rule context="//SENDER-RECEIVER-INTERFACE/SHORT-NAME">
      <assert test="string-length(normalize-space(@name)) &gt; 0 and not(contains(@name,' '))">SRI SHORT-NAME/@name must be non-empty and contain no spaces (simplified C-identifier check).</assert>
    </rule>


      <!-- Rule 31: Each Sender-Receiver interface referenced by a CAN-BUS or Eth-Switch must have at least one DATA-ELEMENTS/VARIABLE-DATA-PROTOTYPE. -->
      <rule context="//CAN-BUS | //Eth-Switch">
        <let name="sri_ref" value="INTERFACE-TREF/@DEST"/>
        <assert test="/AR-PACKAGE/ELEMENTS/SENDER-RECEIVER-INTERFACE[SHORT-NAME/@name = substring-after($sri_ref, '/')]/DATA-ELEMENTS/VARIABLE-DATA-PROTOTYPE">
          The SENDER-RECEIVER-INTERFACE referenced by this CAN-BUS or Eth-Switch must have at least one DATA-ELEMENTS/VARIABLE-DATA-PROTOTYPE (i.e., not empty). This ensures the SRI is valid for network use.
        </assert>
      </rule>

    <!-- Rule 34: Each Data Element has a unique name within the sender-receiver interface. -->
    <rule context="//SENDER-RECEIVER-INTERFACE/DATA-ELEMENTS/VARIABLE-DATA-PROTOTYPE">
      <assert test="not(SHORT-NAME/@name = preceding-sibling::VARIABLE-DATA-PROTOTYPE/SHORT-NAME/@name)">
        Rule 34 violated: VARIABLE-DATA-PROTOTYPE SHORT-NAME '<value-of select="SHORT-NAME/@name"/>' is not unique within this SENDER-RECEIVER-INTERFACE. Each data element must have a unique name within its interface.
      </assert>
    </rule>

      <!-- Rule 34: Each Data Element has a valid data type - Generic_Hardware only supports uint8. -->
      <!-- For SRIs connected to Generic_Hardware, all Data Elements must be Array-of-uint8, not Array-of-float. -->
      <rule context="//SENDER-RECEIVER-INTERFACE">
        <let name="sri_name" value="SHORT-NAME/@name"/>
        <!-- Check if this SRI is referenced by any Generic_Hardware port -->
        <let name="is_connected_to_gh" value="count(//Generic_Hardware//*[self::P-PORT-PROTOTYPE or self::R-PORT-PROTOTYPE]//*[self::PROVIDED-INTERFACE-TREF or self::REQUIRED-INTERFACE-TREF][contains(@DEST, $sri_name)]) &gt; 0"/>
        <!-- If connected to Generic_Hardware, must not have Array-of-float -->
        <assert test="not($is_connected_to_gh) or count(DATA-ELEMENTS//VARIABLE-DATA-PROTOTYPE//TYPE-TREF//Array-of-float) = 0">
          Rule 34 violated: Sender-Receiver Interface '<value-of select="$sri_name"/>' is connected to Generic_Hardware. Data Element can NOT be of type Array-of-float. Data Element type must be uint8 for Sender-Receiver Interfaces connected to Generic_Hardware.
        </assert>
      </rule>
      <!-- Additional validation: Array-of-uint8 with Generic_Hardware should have Random-Values-generated -->
      <rule context="//AR-PACKAGE/ELEMENTS/ECUs/SoCs[Generic_Hardware]">
        <assert test="count(//SENDER-RECEIVER-INTERFACE//TYPE-TREF/Array-of-uint8/Random-Values-generated) &gt; 0">
          Array-of-uint8 used with Generic_Hardware should have Random-Values-generated (or Fixed-values-generated depending on policy).
        </assert>
        <assert test="count(//SENDER-RECEIVER-INTERFACE//TYPE-TREF/Array-of-uint8/Random-Values-generated/Data-Range[@min &lt; @max]) &gt; 0">
          Random-Values-generated Data-Range must have @min &lt; @max.
        </assert>
      </rule>

    <!-- Rule 35: Each Data Element name is valid against basic C naming constraints (non-empty, no spaces). -->
    <!-- Keep this basic in Schematron to avoid redundancy; full regex and keyword checks are enforced in Python. -->
    <rule context="//SENDER-RECEIVER-INTERFACE/DATA-ELEMENTS/VARIABLE-DATA-PROTOTYPE/SHORT-NAME">
      <assert test="string-length(normalize-space(@name)) &gt; 0 and not(contains(@name,' '))">
        Rule 35 (basic) violated: Data Element SHORT-NAME/@name must be non-empty and contain no spaces.
      </assert>
    </rule>

    <!-- Rule 35: Each Data Element with Random Data Generation with boundries has valid boundries. -->
    <rule context="//SENDER-RECEIVER-INTERFACE//Random-Values-generated/Data-Range">
      <assert test="number(@min) &lt; number(@max)">Random-Values-generated Data-Range @min must be less than @max.</assert>
    </rule>
  </pattern>

  <!-- Prebuilt Apps (Rules 36-39) -->
  <pattern id="prebuilt-apps">
    <!-- Rule 36: Each prebuilt app has a unique name. -->
    <rule context="//PrebuiltApp">
      <assert test="not(@name = preceding::PrebuiltApp/@name)">Each prebuilt app must have a unique @name.</assert>
    </rule>

       <!-- Rule 37: Each prebuilt app is mapped to a valid cluster/core. -->
       <rule context="//Core-PrebuiltApplication-Mapping | //Cluster-PrebuiltApplication-Mapping">
         <!-- Conservative: ensure PrebuiltApplicationRef or PATH/@DEST exists; use Python for strict resolution to PRE-BUILT-APPLICATION entries. -->
         <assert test="string-length(@PrebuiltApplicationRef) &gt; 0 or string-length(PATH/@DEST) &gt; 0">
           Prebuilt application mapping should specify a PrebuiltApplicationRef or PATH/@DEST. Use Python for exact resolution to PRE-BUILT-APPLICATION entries.
         </assert>
       </rule>

       <!-- Rule 38: Each prebuilt app has a unique name. -->
       <!-- Rule 39: Each prebuilt app is mapped to a valid cluster/core. -->
       <!-- Rule 40: Each prebuilt app is compiled with the right toolchain. -->
       <rule context="//PRE-BUILT-APPLICATION">
         <let name="appName" value="SHORT-NAME/@name"/>
         <let name="appPath" value="concat('/', $appName)"/>

         <!-- Rule 38: Unique name check -->
         <assert test="not(preceding::PRE-BUILT-APPLICATION[SHORT-NAME/@name = $appName])">
           Rule 38 violated: PRE-BUILT-APPLICATION name '<value-of select="$appName"/>' is duplicated. Each prebuilt app must have a unique name.
         </assert>

         <!-- Rule 39: Mapping check -->
         <assert test="count(//Core-PrebuiltApplication-Mapping[@PrebuiltApplicationRef = $appPath]) + count(//Cluster-PrebuiltApplication-Mapping[@PrebuiltApplicationRef = $appPath]) &gt; 0">
           Rule 39 violated: PRE-BUILT-APPLICATION '<value-of select="$appName"/>' (expected ref: '<value-of select="$appPath"/>') is not mapped to any cluster or core. Each prebuilt app must be referenced by at least one mapping.
         </assert>

         <!-- Rule 40: Toolchain check - not implementable in Schematron -->
         <assert test="true()">IMPLEMENTATION-NOTE: toolchain/compile verification cannot be performed reliably in Schematron. Implement this in CI/build pipelines or in `logical_validator.py` by invoking the toolchain, checking binary symbols/headers, or using file metadata.</assert>
       </rule>

       <!-- Rule 38b: Each prebuilt app path must exist and a valid executable. -->
       <!-- Conservative Schematron check: ensure PATH/@DEST is present and looks like a filename (contains an extension).
            This is NOT a filesystem/execute check — Schematron cannot verify that the file actually exists or is executable. -->
       <rule context="//PRE-BUILT-APPLICATION/PATH">
         <assert test="string-length(normalize-space(@DEST)) &gt; 0 and contains(@DEST, '.')">
           PRE-BUILT-APPLICATION PATH/@DEST must be non-empty and look like a filename (contain an extension). Actual file existence and executable permissions must be checked by the Python validator or CI.
         </assert>
       </rule>

  </pattern>

  <!-- Network Topology (Rule 42) -->
  <pattern id="network-topology">
    <!-- Rule 42: For InterECU communication, Each Interface Reference must be connected to a valid Sender-Receiver Interface. -->
    <!-- NOTE: This is already enforced by Rule 31 above, which validates INTERFACE-TREF/@DEST in CAN-BUS/Eth-Switch
         elements to ensure they resolve to existing SENDER-RECEIVER-INTERFACEs with at least one data element.
         Rule 31 checks: /AR-PACKAGE/ELEMENTS/SENDER-RECEIVER-INTERFACE[SHORT-NAME/@name = substring-after($sri_ref, '/')]
         This satisfies both Rule 31 (non-empty SRI) and Rule 42 (valid SRI reference). -->
  </pattern>

  <!-- HW Validations (Rules 41-73) -->
  <pattern id="hw-validations">
    <!-- Rule 43: Each Ecu has a unique name. -->
    <rule context="//ECUs">
      <assert test="not(SHORT-NAME/@name = preceding::ECUs/SHORT-NAME/@name)">Each ECU must have a unique SHORT-NAME/@name.</assert>
    </rule>

    <!-- Rule 44: Each Ecu name is valid against C variable naming rules (basic check: no spaces). -->
    <rule context="//ECUs/SHORT-NAME">
      <assert test="string-length(normalize-space(@name)) &gt; 0 and not(contains(@name, ' '))">
        Rule 44 violated (partial): ECU SHORT-NAME/@name '<value-of select="@name"/>' contains spaces or is empty. Full C identifier validation (regex, keywords) is performed by Python.
      </assert>
    </rule>

    <!-- Rules 45, 47, 49, 67 combined (same context //ECUs/SoCs) -->
    <rule context="//ECUs/SoCs">
      <!-- Rule 45: Each SoC has a unique name within its ECU. -->
      <assert test="not(SHORT-NAME/@name = preceding-sibling::SoCs/SHORT-NAME/@name)">Each SoC within the same ECU must have a unique SHORT-NAME/@name.</assert>
      <!-- Rule 47: Each SoC has at least one of {Chiplet, Generic Hardware, CPU Cluster}. -->
      <assert test="count(Chiplet) + count(Generic_Hardware) + count(CPU_Cluster) &gt;= 1">Each SoC must contain at least one of Chiplet, Generic_Hardware, or CPU_Cluster.</assert>
      <!-- Rule 49: Each SoC can have only one SoC top level or chiplet with native Ethernet interface.
           Count both: SoC-level ETHERNET-INTERFACE[@Mode='native'] + all Chiplet ETHERNET-INTERFACE[@Mode='native']
           Total must be <= 1 -->
      <assert test="count(ETHERNET-INTERFACE[@Mode='native']) + count(.//Chiplet/ETHERNET-INTERFACE[@Mode='native']) &lt;= 1">
        Rule 49 violated: Each SoC can have at most one native Ethernet interface (either at SoC top-level or in one chiplet). Found <value-of select="count(ETHERNET-INTERFACE[@Mode='native']) + count(.//Chiplet/ETHERNET-INTERFACE[@Mode='native'])"/> native Ethernet interface(s) in SoC '<value-of select="SHORT-NAME/@name"/>'.
      </assert>
      <!-- Rule 67: Number of Hwip instances in each soc top level is maximum 32. -->
      <!-- NOTE: Counts only DIRECT Generic_Hardware children of SoC (not those nested in Chiplets) -->
      <assert test="count(Generic_Hardware) &lt;= 32">Rule 67 violated: Each SoC must not have more than 32 Generic_Hardware (HWIP) instances at SoC level. Found <value-of select="count(Generic_Hardware)"/> instances in SoC '<value-of select="SHORT-NAME/@name"/>'.</assert>
      <!-- Rule 71: Total Number of Chiplets in each SoC is maximum 4, with specific CPU_Cluster placement constraints:
           - Option A: 3 chiplets + 1 CPU_Cluster at SoC top-level (count(CPU_Cluster) = 1 and count(Chiplet) <= 3)
           - Option B: 4 chiplets + 0 CPU_Cluster at SoC top-level (count(CPU_Cluster) = 0 and count(Chiplet) <= 4) -->
      <assert test="(count(CPU_Cluster) = 1 and count(Chiplet) &lt;= 3) or (count(CPU_Cluster) = 0 and count(Chiplet) &lt;= 4)">
        Rule 71 violated: Each SoC must have either (3 chiplets + 1 CPU_Cluster at SoC top-level) OR (4 chiplets + 0 CPU_Cluster at SoC top-level). Found <value-of select="count(Chiplet)"/> Chiplet(s) and <value-of select="count(CPU_Cluster)"/> CPU_Cluster(s) at SoC top-level in SoC '<value-of select="SHORT-NAME/@name"/>'.
      </assert>
    </rule>

    <!-- Rule 46: Each SoC name is valid against C variable naming rules (basic check: no spaces). -->
    <rule context="//ECUs/SoCs/SHORT-NAME">
      <assert test="string-length(normalize-space(@name)) &gt; 0 and not(contains(@name, ' '))">
        Rule 46 violated (partial): SoC SHORT-NAME/@name '<value-of select="@name"/>' contains spaces or is empty. Full C identifier validation (regex, keywords) is performed by Python.
      </assert>
    </rule>



    <!-- Rule 50: Number of Socs in the System is maximum 100 -->
    <rule context="/">
      <assert test="count(.//SoCs) &lt;= 100">Rule 50 violated: Total number of SoCs in the system must not exceed 100. Found <value-of select="count(.//SoCs)"/> SoC(s).</assert>
    </rule>

    <!-- Rule 51: Each Chiplet has a unique name within the SoC. -->
    <!-- Rules 51, 53, 68: Chiplet-level validations (merged to avoid context conflict) -->
    <rule context="//Chiplet">
      <!-- Rule 51: Each Chiplet within the same SoC must have a unique SHORT-NAME. -->
      <assert test="not(SHORT-NAME/@name = preceding-sibling::Chiplet/SHORT-NAME/@name)">
        Rule 51 violated: Each Chiplet within the same SoC must have a unique SHORT-NAME. Found duplicate name '<value-of select="SHORT-NAME/@name"/>' in SoC '<value-of select="../SHORT-NAME/@name"/>'.
      </assert>
      <!-- Rule 53: Each Chiplet has at least one of {Generic Hardware, CPU Cluster}. -->
      <assert test="count(Generic_Hardware) + count(CPU_Cluster) &gt;= 1">
        Rule 53 violated: Each Chiplet must contain at least one of Generic_Hardware or CPU_Cluster. Found <value-of select="count(Generic_Hardware) + count(CPU_Cluster)"/> in Chiplet '<value-of select="SHORT-NAME/@name"/>'.
      </assert>
      <!-- Rule 68: Number of Hwip instances in each Chiplet is maximum 32. -->
      <!-- NOTE: Counts only DIRECT Generic_Hardware children of Chiplet (same level) -->
      <assert test="count(Generic_Hardware) &lt;= 32">Rule 68 violated: Each Chiplet must not have more than 32 Generic_Hardware (HWIP) instances. Found <value-of select="count(Generic_Hardware)"/> instances in Chiplet '<value-of select="SHORT-NAME/@name"/>'.</assert>
    </rule>

    <!-- Rule 52: Each Chiplet name is valid against C variable naming rules. -->
    <rule context="//Chiplet/SHORT-NAME">
      <!-- Simplified C-style check: non-empty and no spaces. For full regex use XPath 2.0 or Python. -->
      <assert test="string-length(normalize-space(@name)) &gt; 0 and not(contains(@name, ' '))">
        Rule 52 violated (partial): Chiplet SHORT-NAME/@name '<value-of select="@name"/>' contains spaces or is empty. Full C identifier validation (regex, keywords) is performed by Python.
      </assert>
    </rule>

    <!-- Rule 55: Each HWIP (Generic_Hardware) has a unique name within the Chiplet/SoC Top Level. -->
    <rule context="//Generic_Hardware">
        <let name="hwip_name" value="SHORT-NAME/@name"/>
        <let name="p_port_count" value="count(.//INTERNAL-BEHAVIOR/PORTS/P-PORT-PROTOTYPE)"/>
        <let name="r_port_count" value="count(.//INTERNAL-BEHAVIOR/PORTS/R-PORT-PROTOTYPE)"/>

        <!-- Rule 55: HWIP name uniqueness -->
      <assert test="not(SHORT-NAME/@name = preceding-sibling::Generic_Hardware/SHORT-NAME/@name)">
        Rule 55 violated: Each Generic_Hardware (HWIP) within the same parent (Chiplet or SoC) must have a unique SHORT-NAME. Found duplicate name '<value-of select="SHORT-NAME/@name"/>' in parent '<value-of select="../SHORT-NAME/@name"/>'.
      </assert>

        <!-- Rule 61: Maximum 32 ports of each type -->
        <assert test="$p_port_count &lt;= 32">
          Rule 61 violated: HWIP '<value-of select="$hwip_name"/>' has <value-of select="$p_port_count"/> P-PORT-PROTOTYPE elements, exceeding the maximum limit of 32.
        </assert>

        <assert test="$r_port_count &lt;= 32">
          Rule 61 violated: HWIP '<value-of select="$hwip_name"/>' has <value-of select="$r_port_count"/> R-PORT-PROTOTYPE elements, exceeding the maximum limit of 32.
        </assert>
    </rule>

    <!-- Rule 56: Each HWIP (Generic_Hardware) name is valid against C variable naming rules (basic check). -->
    <rule context="//Generic_Hardware/SHORT-NAME">
      <assert test="string-length(normalize-space(@name)) &gt; 0 and not(contains(@name, ' '))">
        Rule 56 violated (partial): Generic_Hardware SHORT-NAME/@name '<value-of select="@name"/>' contains spaces or is empty. Full C identifier validation (regex, keywords) is performed by Python.
      </assert>
    </rule>

    <!-- Rules 57, 58, 59, 60: HWIP Port validations (combined due to same context) -->
    <rule context="//Generic_Hardware/INTERNAL-BEHAVIOR/PORTS/P-PORT-PROTOTYPE">
      <!-- Define variables for all checks -->
      <let name="hwip_name" value="ancestor::Generic_Hardware/SHORT-NAME/@name"/>
      <let name="port_name" value="SHORT-NAME/@name"/>
      <let name="p_sri" value="PROVIDED-INTERFACE-TREF/@DEST"/>

      <!-- Rule 57: Port name uniqueness within HWIP -->
      <assert test="not(SHORT-NAME/@name = preceding-sibling::*/SHORT-NAME/@name)">
        Rule 57 violated: Each port (P-PORT-PROTOTYPE or R-PORT-PROTOTYPE) within the same Generic_Hardware must have a unique SHORT-NAME. Found duplicate port name '<value-of select="SHORT-NAME/@name"/>' in Generic_Hardware '<value-of select="$hwip_name"/>'.
      </assert>

      <!-- Rule 58: Port interface reference format (Python validates existence) -->
      <assert test="string-length(PROVIDED-INTERFACE-TREF/@DEST) &gt; 0 and contains(PROVIDED-INTERFACE-TREF/@DEST, '/')">
        Rule 58 violated (partial): HWIP Provider port must have a non-empty PROVIDED-INTERFACE-TREF/@DEST that looks like a path. (Python validates that the referenced SRI actually exists.)
      </assert>

      <!-- Rule 59: Port must be connected to at least one operation -->
      <assert test="count(ancestor::Generic_Hardware//OPERATIONS-SEQUENCE//WRITE[contains(IREF/@DEST, $port_name)]) &gt;= 1">
        Rule 59 violated (partial): HWIP Provider port '<value-of select="$port_name"/>' in Generic_Hardware '<value-of select="$hwip_name"/>' must be referenced by at least one WRITE operation. (Python validates exact path matching.)
      </assert>

      <!-- Rule 60: HWIP cannot have P-PORT and R-PORT connected to same SRI -->
      <assert test="not($p_sri = ../R-PORT-PROTOTYPE/REQUIRED-INTERFACE-TREF/@DEST)">
        Rule 60 violated: HWIP '<value-of select="$hwip_name"/>' has both P-PORT '<value-of select="$port_name"/>' and R-PORT connected to the same SRI '<value-of select="$p_sri"/>'. Each HWIP can NOT have provider and required ports connected to the same Sender-Receiver Interface.
      </assert>
    </rule>

    <rule context="//Generic_Hardware/INTERNAL-BEHAVIOR/PORTS/R-PORT-PROTOTYPE">
      <!-- Define variables for all checks -->
      <let name="hwip_name" value="ancestor::Generic_Hardware/SHORT-NAME/@name"/>
      <let name="port_name" value="SHORT-NAME/@name"/>
      <let name="r_sri" value="REQUIRED-INTERFACE-TREF/@DEST"/>

      <!-- Rule 57: Port name uniqueness within HWIP -->
      <assert test="not(SHORT-NAME/@name = preceding-sibling::*/SHORT-NAME/@name)">
        Rule 57 violated: Each port (P-PORT-PROTOTYPE or R-PORT-PROTOTYPE) within the same Generic_Hardware must have a unique SHORT-NAME. Found duplicate port name '<value-of select="SHORT-NAME/@name"/>' in Generic_Hardware '<value-of select="$hwip_name"/>'.
      </assert>

      <!-- Rule 58: Port interface reference format (Python validates existence) -->
      <assert test="string-length(REQUIRED-INTERFACE-TREF/@DEST) &gt; 0 and contains(REQUIRED-INTERFACE-TREF/@DEST, '/')">
        Rule 58 violated (partial): HWIP Required port must have a non-empty REQUIRED-INTERFACE-TREF/@DEST that looks like a path. (Python validates that the referenced SRI actually exists.)
      </assert>

      <!-- Rule 59: Port must be connected to at least one operation -->
      <assert test="count(ancestor::Generic_Hardware//OPERATIONS-SEQUENCE//READ[contains(IREF/@DEST, $port_name)]) &gt;= 1">
        Rule 59 violated (partial): HWIP Required port '<value-of select="$port_name"/>' in Generic_Hardware '<value-of select="$hwip_name"/>' must be referenced by at least one READ operation. (Python validates exact path matching.)
      </assert>

      <!-- Rule 60: HWIP cannot have P-PORT and R-PORT connected to same SRI -->
      <assert test="not($r_sri = ../P-PORT-PROTOTYPE/PROVIDED-INTERFACE-TREF/@DEST)">
        Rule 60 violated: HWIP '<value-of select="$hwip_name"/>' has both R-PORT '<value-of select="$port_name"/>' and P-PORT connected to the same SRI '<value-of select="$r_sri"/>'. Each HWIP can NOT have provider and required ports connected to the same Sender-Receiver Interface.
      </assert>
    </rule>

    <!-- Removed legacy D2D Schematron check (handled in Python). The old rule used legacy names
         (D2D-Configuration/@DEST) and did not align with the XSD (D2D_Configuration/DestChipletRef).
         Python now performs strict cross-reference validation for Rule 48. -->

    <!-- Rule 53: Each Hwip has a unique name within the Chiplet/Soc Top Level. -->
    <rule context="//Hwip">
      <assert test="not(@name = preceding::Hwip/@name)">Hwip @name must be unique within the document/scope.</assert>
    </rule>

    <!-- Rule 54: Each Hwip name is valid against C variable naming rules. -->
    <rule context="//Hwip">
      <assert test="string-length(normalize-space(@name)) &gt; 0 and not(contains(@name,' '))">Hwip @name must be non-empty and contain no spaces (simplified C-identifier check).</assert>
    </rule>

    <!-- Rule 55: Each Hwip Port name is unique within the Hwip. -->
    <rule context="//Hwip/Port">
      <assert test="not(@name = preceding-sibling::Port/@name)">Hwip Port names should be unique within the Hwip.</assert>
    </rule>

    <!-- Rule 56: Each Hwip Port is connected to a valid Sender-Receiver Interface. -->
    <rule context="//Hwip/Port">
      <!-- Conservative: ensure PORT-REF/@DEST exists and looks like a path. Python required for exact SRI matching. -->
      <assert test="count(.//PORT-REF/@DEST) &gt; 0 and string-length(.//PORT-REF/@DEST) &gt; 0">Hwip Port must include PORT-REF/@DEST that looks like a path. Use Python for exact matching to SENDER-RECEIVER-INTERFACE SHORT-NAME.</assert>
    </rule>

    <!-- Rule 57: Each Hwip Port is connected to at least one valid operation. -->
    <rule context="//Hwip/Port">
      <assert test="count(.//Operation) &gt;= 1 or count(.//READ) + count(.//WRITE) &gt;= 1">Hwip Port must have at least one Operation (READ/WRITE or Operation child) connected.</assert>
    </rule>

    <!-- Rule 58: Each Hwip can NOT have provider and required ports connected to the same Sender-Receiver Interface. -->
    <rule context="//Hwip">
      <!-- Conservative check: ensure Provider and Required ports do not both reference identical PORT-REF/@DEST strings at the same Hwip level. If complex nesting exists, use Python. -->
      <assert test="not(.//Port[Provider and .//PORT-REF/@DEST = ../Port[Required]//PORT-REF/@DEST])">Hwip must not have Provider and Required ports pointing to the same PORT-REF/@DEST. Use Python for robust matching across nested structures.</assert>
    </rule>

    <!-- Rule 61: Each Hwip has maximum 32 ports of each type. -->
    <rule context="//Hwip">
      <assert test="count(.//Port[Provider]) &lt;= 32 and count(.//Port[Required]) &lt;= 32">Each Hwip must not have more than 32 Provider or Required ports.</assert>
    </rule>

    <!-- Rule 62: Each Hwip Operations are valid. -->
    <!-- PYTHON-ONLY: This rule requires comprehensive semantic validation that Schematron cannot perform:
         - Port reference resolution (verify IREF DEST points to existing ports)
         - Semantic type checking (READ must point to R-PORT, WRITE to P-PORT)
         - ML operation parameter validation (non-zero dimensions)
         - CUSTOM-OPERATION validation (handled by Rule 25 in Python)
         See python_logical_validations.py _validate_rule_62() for implementation. -->

    <!-- Rule 63: Each Hwip Read/Write operation is connected to a valid port. -->
    <!-- PYTHON-ONLY: This rule validates READ/WRITE port **connectivity** (separate from Rule 62).
         Rule 62 validates operations are VALID (well-formed, correct structure/values).
         Rule 63 validates operations are CONNECTED (port resolution, semantic correctness).

         This rule requires Python because it needs to:
         - Resolve IREF DEST paths to actual ports in the HWIP
         - Verify ports actually exist (not just non-empty paths)
         - Check semantic correctness (READ→R-PORT, WRITE→P-PORT)

         See python_logical_validations.py _validate_rule_63() for implementation. -->

    <!-- Rule 64: Each Hwip Data Received event is connected to a valid port.
         PYTHON-ONLY VALIDATION - Schematron cannot resolve REQUIRED-PORT-TREF references.
         Requires:
         1. Resolving REQUIRED-PORT-TREF to actual ports within the HWIP
         2. Verifying port exists in the HWIP's PORTS collection
         3. Semantic validation: REQUIRED-PORT-TREF must point to R-PORT-PROTOTYPE (not P-PORT)
         4. Structural validation: REQUIRED-PORT-TREF must not be empty
         See python_logical_validations.py _validate_rule_64() for implementation. -->

    <!-- Rule 65: Each Hwip Trigger event is connected to a valid Runnable/Event.
         PYTHON-ONLY VALIDATION - Schematron cannot resolve TRIGGER DEST references.
         Requires:
         1. Resolving TRIGGER DEST to find target element (RUNNABLE-ENTITY, Event, Operation, Interface)
         2. Verifying target exists in the document
         3. Semantic validation: DEST must point to valid trigger target types
         4. Structural validation: TRIGGER DEST must not be empty
         See python_logical_validations.py _validate_rule_65() for implementation. -->

    <!-- Old Schematron attempt for Rule 65 - DISABLED (cannot validate references) -->
    <!-- <rule context="//Hwip//TRIGGER-EVENT | //Hwip//TIMING-EVENT">
      <assert test="count(.//Runnable) or count(ancestor::RUNNABLE-ENTITY) &gt; 0">Trigger events should be inside or reference a RUNNABLE-ENTITY.</assert>
    </rule> -->

    <!-- Rule 66: Each Hwip Trigger Runnable/Event is mapped to a core in same Chiplet/Soc Top Level.
         PYTHON-ONLY VALIDATION - Schematron cannot perform cross-element hierarchy comparison.
         Requires:
         1. Resolving TRIGGER DEST to target runnable
         2. Finding Core-Runnable-Mapping for that runnable (ClusterRef)
         3. Parsing ClusterRef path to extract SoC/Chiplet location
         4. Determining HWIP's parent SoC/Chiplet in document hierarchy
         5. Comparing locations to ensure same SoC/Chiplet
         6. Detecting unmapped runnables
         See python_logical_validations.py _validate_rule_66() for implementation. -->

    <!-- Old Schematron attempt for Rule 66 - DISABLED (cannot validate cross-element mappings) -->
    <!-- <rule context="//Hwip//TRIGGER-EVENT">
      <assert test="true()">IMPLEMENTATION-NOTE: verify Trigger Runnable/Event mapping to a Core in the same Chiplet/SoC; this requires cross-element mapping and may be better in Python.</assert>
    </rule> -->

    <!-- Rule 67: Moved to line ~530 (combined with Rules 45, 47, 49 in context //ECUs/SoCs) -->

    <!-- Rule 68: Moved to line ~565 (combined with Rules 51, 53 in context //Chiplet) -->

    <!-- ============================================================================
         CPU_Cluster-level validations (Rules 67, 70, 72, 73)
         NOTE: Schematron applies only ONE rule per context in a pattern.
         Consolidated into a single rule context for //CPU_Cluster to ensure all assertions fire.
         ============================================================================ -->
    <rule context="//CPU_Cluster">
      <!-- Rule 67: Each CPU cluster has a unique name (legacy attribute-based; modern schema uses child SHORT-NAME) -->
      <assert test="not(@name = preceding::CPU_Cluster/@name)">CPU_Cluster @name must be unique within the document/scope.</assert>

      <!-- Rule 70: IMPLEMENTATION-NOTE - OS type and name C-identifier validation in Python -->
      <assert test="true()">IMPLEMENTATION-NOTE: CPU_Cluster OS type and name C-identifier validation performed in Python Rule 70. Core-specific OS restrictions (M7/R52 must use Nucleus_RTOS) validated in Python Rule 72.</assert>

      <!-- Rule 73: Each CPU cluster running Linux must use only supported filesystems.
           We enable a conservative Schematron check here so policy violations surface during
           the Schematron stage. Allowed filesystem child elements: Ubuntu_File_System, Buildroot_File_System.
      -->
      <assert test="not(Operating-System/Linux/*[not(local-name() = 'Ubuntu_File_System' or local-name() = 'Buildroot_File_System')])">
        Rule 73 violated: CPU_Cluster running Linux contains an unsupported filesystem element. Supported filesystem elements: Ubuntu_File_System, Buildroot_File_System.
      </assert>

      <!-- Rule 72: Each CPU cluster can either be connected to a runnable or prebuilt app mappings, not both -->
      <assert test="not((.//Core-Runnable-Mapping or .//Core-runnable-Mapping) and (.//Core-PrebuiltApplication-Mapping or .//Cluster-PrebuiltApplication-Mapping))">CPU_Cluster must not be mapped to both runnables and prebuilt apps simultaneously.</assert>

      <!-- Rule 76 (HW): CPU Cluster Frequency must be 1000000000 Hz (1 GHz) for Linux OS -->
      <assert test="not(Operating-System/Linux and .//Frequency[@value != '1000000000'])">
        Rule 76 (HW) violated: CPU_Cluster running Linux OS must have Frequency value="1000000000" (1 GHz). Found: <value-of select=".//Frequency/@value"/> Hz.
      </assert>
    </rule>

    <!-- Rule 70: Each CPU cluster name is valid against C variable naming rules (basic check: no spaces, non-empty). -->
    <rule context="//CPU_Cluster//*[starts-with(local-name(), 'Cortex')]/SHORT-NAME">
      <assert test="string-length(normalize-space(@name)) &gt; 0 and not(contains(@name,' '))">
        Rule 70 violated (partial): CPU_Cluster SHORT-NAME '@name='<value-of select="@name"/>' contains spaces or is empty. Full C identifier validation (regex, keywords) is performed by Python.
      </assert>
    </rule>

    <!-- Rule 73 (nucleus-specific): Each CPU cluster running nucleus OS must be mapped to a runnable -->
    <rule context="//CPU_Cluster[Operating-System/Nucleus_RTOS]">
      <assert test="(.//Core-Runnable-Mapping or .//Core-runnable-Mapping)">CPU_Cluster with Nucleus_RTOS Operating-System must have Runnable mapping(s).</assert>
    </rule>
  </pattern>

  <!-- HW-SW mapping (Rules 74-78) -->
  <pattern id="hw-sw-mapping">
    <!-- Rule 74: Each HwSwMapping is connected to a valid cpu cluster -->
    <rule context="//HwSwMapping | //HW-SW-MAPPING">
      <!-- Conservative check: ClusterRef attribute should be present and look like a path; full resolution to a CPU_Cluster SHORT-NAME requires Python. -->
      <assert test="string-length(@ClusterRef) &gt; 0 and contains(@ClusterRef, '/')">
        HwSwMapping/@ClusterRef must be present and look like a path. For robust resolution to CPU_Cluster SHORT-NAME or to handle duplicate names, use the Python validator.
      </assert>
      <assert test="true()">IMPLEMENTATION-NOTE: This is a conservative check; if DESTs have different formatting or there are duplicate SHORT-NAMEs across ECUs/SoCs, implement robust resolution in `logical_validator.py`.</assert>
    </rule>

    <!-- Rule 75: Each CoreRunnableMapping has a valid CoreId value -->
    <rule context="//Core-Runnable-Mapping | //CoreRunnableMapping">
      <!-- Basic numeric/format check: CoreId must be an integer and within XSD allowed bounds (0..7). -->
      <assert test="string(number(@CoreId)) != 'NaN' and number(@CoreId) &gt;= 0 and number(@CoreId) &lt;= 7">
        Core-Runnable-Mapping/@CoreId must be numeric and within 0..7 (XSD also constrains this). For exact check against the target cluster's CoresPerCluster use Python.
      </assert>
      <assert test="true()">IMPLEMENTATION-NOTE: To ensure CoreId &lt; CoresPerCluster of the referenced cluster requires resolving the ClusterRef and reading CoresPerCluster — better done in Python.</assert>
    </rule>

    <!-- Rule 76: Each CoreRunnableMapping is connected to a valid runnable -->
    <rule context="//Core-Runnable-Mapping | //CoreRunnableMapping">
      <!-- Conservative: ensure RunnableRef attribute is present and looks like a path. Use Python to resolve to actual RUNNABLE-ENTITY declarations. -->
      <assert test="string-length(@RunnableRef) &gt; 0 and contains(@RunnableRef, '/')">
        Core-Runnable-Mapping/@RunnableRef must be present and look like a path. Use Python for strict resolution to RUNNABLE-ENTITY declarations.
      </assert>
      <assert test="true()">IMPLEMENTATION-NOTE: If RunnableRef uses a different path format or needs full-scope resolution, implement in Python.</assert>
    </rule>

    <!-- Rule 77: Each CorePrebuiltAppMapping has a valid CoreId value -->
    <rule context="//Core-PrebuiltApplication-Mapping | //CorePrebuiltAppMapping">
      <assert test="string(number(@CoreId)) != 'NaN' and number(@CoreId) &gt;= 0 and number(@CoreId) &lt;= 7">
        Core-PrebuiltApplication-Mapping/@CoreId must be numeric and within 0..7 (XSD also constrains this).
      </assert>
      <!-- Conservative check: ensure PrebuiltApplicationRef or PATH/@DEST exists; use Python for strict resolution to PRE-BUILT-APPLICATION entries. -->
      <assert test="string-length(@PrebuiltApplicationRef) &gt; 0 or string-length(PATH/@DEST) &gt; 0">
        Core-PrebuiltApplication-Mapping must specify a PrebuiltApplicationRef or provide a PATH/@DEST. Use Python to verify it matches a declared PRE-BUILT-APPLICATION.
      </assert>
      <assert test="true()">IMPLEMENTATION-NOTE: Cross-checking CoreId against the actual cluster size requires resolving the mapping's ClusterRef — use Python for robust checks.</assert>
    </rule>

    <!-- Rule 78: Each ClusterPrebuiltAppMapping is connected to a valid prebuilt application -->
    <!-- (placeholders above; replace test="true()" with concrete XPath rules) -->
    <rule context="//Cluster-PrebuiltApplication-Mapping | //ClusterPrebuiltAppMapping">
      <!-- Conservative check: ensure PrebuiltApplicationRef or PATH/@DEST exists; use Python to resolve to PRE-BUILT-APPLICATION entries. -->
      <assert test="string-length(@PrebuiltApplicationRef) &gt; 0 or string-length(PATH/@DEST) &gt; 0">
        Cluster-PrebuiltApplication-Mapping must specify a PrebuiltApplicationRef or provide a PATH/@DEST. Use Python for strict resolution to PRE-BUILT-APPLICATION entries and filesystem checks.
      </assert>
      <assert test="true()">IMPLEMENTATION-NOTE: This checks only that the prebuilt application is declared. To verify the binary exists on disk or is compatible with the target cluster, use Python/CI.</assert>
    </rule>
  </pattern>

  <!-- Analysis (Rules 79-82) -->
  <pattern id="analysis-checks">
    <!-- Rule 79: Each Analysis Soc reference is connected to a valid Soc. -->
    <!-- Accept both <SocReference DEST="..."> and inline <SoC DEST="..."> under Analysis
         Use rule context on the element with @DEST so we can reference @DEST directly (no current()). -->
    <rule context="//Analysis//SocReference | //Analysis//SoC">
      <!-- Conservative check: ensure the element's @DEST exists and looks like a path. Use Python to strictly ensure it references an existing SoC SHORT-NAME. -->
      <assert test="string-length(@DEST) &gt; 0 and contains(@DEST, '/')">
        Analysis SoC reference must include a non-empty @DEST that looks like a path. Use Python for strict resolution to an existing SoC.
      </assert>
    </rule>

    <!-- Rule 80: If Power Analysis is enabled, then all CPU Clusters type must be in the supported list. -->
    <!-- Rule 81: If Power Analysis is enabled, then all CPU Clusters Os type must be in the supported list. -->
    <!-- Rule 82: If Power Analysis is enabled, then all CPU Clusters must be single core. -->
    <!-- Rule 80-82: Power Analysis conditional checks
         If an <Analysis> element contains a flag/child indicating PowerAnalysis is enabled
         (e.g., <PowerAnalysis enabled="true"/> or @PowerAnalysisEnabled='true'), then enforce:
         - CPU cluster type in supported list
         - CPU cluster OS in supported list
         - CPU cluster must be single-core

         Because the exact marker used to enable power analysis and the representation of CPU cluster
         attributes vary between models, we provide a conservative, configurable set of XPath-1.0
         assertions below and leave an IMPLEMENTATION-NOTE describing when Python/XPath2 is required.
    -->
  <rule context="//Analysis[.//*[local-name() = 'PowerAnalysis' and @enabled='true'] or @PowerAnalysisEnabled='true' or .//*[local-name() = 'Power-Analysis-Enable'] ]">
      <!-- Rule 80: supported CPU cluster type - conservative check: ensure each CPU_Cluster in the document has a supported type -->
      <!-- Use an absolute search (//CPU_Cluster) so we evaluate all clusters in the document even when Analysis is a separate subtree. -->
      <assert test="not(//CPU_Cluster[.//*[starts-with(local-name(),'AFM-') or starts-with(local-name(),'Cortex') or starts-with(local-name(),'RISCV')][not(local-name() = 'CortexA53' or local-name() = 'CortexA57' or local-name() = 'CortexA72' or local-name() = 'CortexR52' or local-name() = 'CortexM7')]])">
        Rule 80: When PowerAnalysis is enabled, CPU_Cluster must use a supported CPU type. Supported nested element local-names (examples): CortexA53, CortexA57, CortexA72, CortexR52, CortexM7. Adjust if your model uses different element names or attributes.
      </assert>

      <!-- Rule 81: supported OS types - check Operating-System child element (not @os attribute) -->
      <!-- Use absolute search to inspect CPU_Cluster elements across the document. -->
      <!-- Check that all CPU_Clusters have Operating-System with Linux, Nucleus_RTOS, or FreeRTOS -->
      <assert test="not(//CPU_Cluster[not(Operating-System/Linux or Operating-System/Nucleus_RTOS or Operating-System/FreeRTOS)])">
        Rule 81: When PowerAnalysis is enabled, all CPU_Cluster Operating-System must be one of the supported OS types: Linux, Nucleus_RTOS, or FreeRTOS.
      </assert>

      <!-- Rule 84: Strict policy - when PowerAnalysis enabled, all CPU_Cluster OS must be Nucleus_RTOS -->
      <!-- Use absolute search so we check all CPU_Cluster elements in the document rather than only those under the Analysis element. -->
      <assert test="not(//CPU_Cluster[Operating-System/*[not(local-name() = 'Nucleus_RTOS')]])">
        Rule 84 violated: When PowerAnalysis is enabled, every CPU_Cluster Operating-System must be 'Nucleus_RTOS'.
      </assert>

      <!-- Rule 82: single-core enforcement - conservative check: ensure CPU_Cluster/@cores exists and equals '1' if present -->
      <!-- Use absolute search so we evaluate cluster attributes across the entire document. -->
      <assert test="not(//CPU_Cluster[@cores and not(number(@cores) = 1)])">
        Rule 82: When PowerAnalysis is enabled, CPU_Cluster must be single-core. This assert treats @cores attribute numerically when present; if cores are modeled differently (child elements or ranges) implement in Python/XPath 2.0.
      </assert>

      <assert test="true()">IMPLEMENTATION-NOTE: The asserts above are conservative XPath-1.0 checks that
        assume CPU_Cluster attributes '@type', '@os' and '@cores' exist and are directly comparable. If your
        model represents these properties differently (e.g., nested elements, enumerations, or requires
        complex matching) implement the checks in `logical_validator.py` or with an XPath 2.0-capable processor.
      </assert>
    </rule>
  </pattern>

  <!-- Rule 21: Each Custom Behavior has a unique name. -->
  <pattern id="custom-behavior-uniqueness">
    <rule context="//SWC-CUSTOM-BEHAVIOR/SHORT-NAME[@name and string-length(normalize-space(@name)) &gt; 0]">
      <assert test="not(@name = preceding::SWC-CUSTOM-BEHAVIOR/SHORT-NAME/@name)">
        Each SWC-CUSTOM-BEHAVIOR must have a unique SHORT-NAME/@name within the document.
      </assert>
    </rule>
  </pattern>

  <!-- Rules 22 & 23: Each Read/Write Operation has a valid Data Access reference. -->
  <!-- Schematron checks structural requirements (IREF presence, non-empty DEST). -->
  <!-- Python validates semantic requirements (DEST resolves to actual DATA-READ-ACCESS or DATA-WRITE-ACCESS). -->
  <pattern id="read-write-operation-data-access">
    <rule context="//READ | //WRITE">
      <assert test="IREF and string-length(normalize-space(IREF/@DEST)) &gt; 0">
        Each <name/> operation must have an IREF child with a non-empty DEST attribute.
      </assert>
    </rule>
  </pattern>

  <!-- Rule 69: Each CPU cluster has a unique name within the Chiplet/SoC Top Level. -->
  <pattern id="cpu-cluster-uniqueness">
    <rule context="//SoCs//CPU_Cluster//SHORT-NAME">
      <let name="this_soc_name" value="ancestor::SoCs/SHORT-NAME/@name"/>
      <assert test="not(@name = preceding::SHORT-NAME[ancestor::CPU_Cluster and ancestor::SoCs/SHORT-NAME/@name = $this_soc_name]/@name)">
        Rule 69 violated: Each CPU_Cluster must have a unique name within the SoC (including CPU_Clusters in Chiplets). Found duplicate CPU_Cluster name '<value-of select="@name"/>' in SoC '<value-of select="$this_soc_name"/>'.
      </assert>
    </rule>
  </pattern>

  <!-- Simulation-Time validation: must be at least 3000 ms -->
  <pattern id="simulation-time-validation">
    <rule context="//Simulation-Time">
      <!-- Convert to ms: us/1000, s*1000, ns/1000000, ms stays as is -->
      <assert test="
        (@unit = 'ms' and number(@value) &gt;= 3000) or
        (@unit = 'us' and number(@value) &gt;= 3000000) or
        (@unit = 's' and number(@value) &gt;= 3) or
        (@unit = 'ns' and number(@value) &gt;= 3000000000) or
        (not(@unit) and number(@value) &gt;= 3000)
      ">
        Simulation-Time must be at least 3000 ms. Found: <value-of select="@value"/> <value-of select="@unit"/>.
      </assert>
    </rule>
  </pattern>

  <!-- DEBUG: force fail if Ubuntu_File_System present -->
</schema>
